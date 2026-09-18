import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import aiofiles
import aiofiles.os
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

from agent.utils.state import CoverageUrlConfig
from agent.config.coverage_config import (
    CoverageAPIConfig, join_paths, to_unc_path,
)
from agent.subgraphs.coverage.utils.coverage_api import coverage_api_call
from agent.subgraphs.coverage.utils.coverage_polling import check_coverage_status
from agent.subgraphs.coverage.utils.get_outer_polygon_from_user_db import (
    get_outer_polygon_from_user_db,
)
from security.encryption.iid_hash_utils import HASHING_ENABLED, reverse_map_hashes
from agent.db.DatabaseManager import get_global_db_manager

logger = logging.getLogger(__name__)

# CWE only processes one job at a time — serialize API submission + polling
_cwe_semaphore = asyncio.Semaphore(1)


async def _create_payload(data: dict, stream_writer: StreamWriter) -> str:
    """Build a JSON payload file on disk for one technology."""
    tech = data["tech"]
    label = tech.upper()
    api_config = CoverageAPIConfig()
    template_path = Path(api_config.payload_template_path)

    if await aiofiles.os.path.exists(template_path):
        async with aiofiles.open(template_path, "r", encoding="utf-8") as f:
            payload = json.loads(await f.read())
    else:
        raise FileNotFoundError(f"Payload template not found at {template_path}")

    cell_ids = data["iids"]
    if cell_ids and HASHING_ENABLED:
        db_mgr = get_global_db_manager()
        async with db_mgr.connection(data["project_name"]) as conn:
            rmap = await reverse_map_hashes(conn, set(cell_ids))
        if rmap:
            cell_ids = [rmap.get(cid, cid) for cid in cell_ids]

    payload["cells"] = cell_ids
    payload["arrayTypes"] = data["array_types"]

    full_output = join_paths(
        api_config.payload_root_output_location,
        data["output_path"] or api_config.payload_default_output_location,
    )
    payload["output"] = {
        "type": api_config.payload_output_type,
        "name": data["output_name"] or api_config.payload_output_name,
        "location": to_unc_path(full_output),
    }

    if data.get("boundaries"):
        payload["extents"]["geometry"]["coordinates"] = data["boundaries"]
    else:
        cords = await get_outer_polygon_from_user_db(
            data["user_email"], data["project_name"],
        )
        payload["extents"]["geometry"]["coordinates"] = cords

    export_folder = Path(api_config.payload_store)
    if not await aiofiles.os.path.exists(export_folder):
        await aiofiles.os.makedirs(export_folder, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = export_folder / f"CWE_cwe_{tech}_{ts}.json"
    async with aiofiles.open(out_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(payload, indent=4))

    stream_writer({
        "step": f"[{label}] Create Payload",
        "status": "completed",
        "message": f"Payload saved: {out_file.name}",
    })
    return str(out_file)


async def coverage_run_tech_pipeline(data: dict):
    """
    Send-target node.  Receives a plain dict (NOT State) from Send(),
    runs the full pipeline for one technology:
        create payload  →  call API  →  poll until done/failed
    Returns a state-update dict writing into the tech_results reducer.
    """
    tech = data["tech"]
    label = tech.upper()
    stream_writer: StreamWriter = get_stream_writer()

    url_cfg = CoverageUrlConfig(**{
        k: v for k, v in data["url_config"].items()
        if k in CoverageUrlConfig.model_fields
    })

    result = {
        "tech": tech,
        "iids": data["iids"],
        "array_types": data["array_types"],
        "output_path": data["output_path"],
        "output_name": data["output_name"],
        "url_config": url_cfg.model_dump(),
    }

    # ── Step 1: Create Payload ────────────────────────────────────────
    try:
        stream_writer({
            "step": f"[{label}] Create Payload",
            "status": "started",
            "message": f"Creating {label} payload ({len(data['iids'])} cells)...",
        })
        payload_file = await _create_payload(data, stream_writer)
        result["payload_file"] = payload_file
    except Exception as e:
        result["success"] = False
        result["error"] = f"Payload failed: {e}"
        stream_writer({
            "step": f"[{label}] Create Payload",
            "status": "failed",
            "message": str(e),
        })
        return {"tech_results": [result]}

    # ── Steps 2+3: serialised — CWE handles one job at a time ────────────────
    async with _cwe_semaphore:
        # Step 2: Call API
        try:
            stream_writer({
                "step": f"[{label}] Call API",
                "status": "started",
                "message": f"Calling coverage API for {label}...",
            })
            resp = await coverage_api_call(
                url_cfg, data["project_name"], payload_file_path=payload_file,
            )
            resp_data = resp.json()
            token = resp_data.get("token")
            if resp.status_code != 201 or token is None:
                raise Exception(f"API error {resp.status_code}: {resp.text}")
            result["token"] = token
            result["api_called"] = True
            stream_writer({
                "step": f"[{label}] Call API",
                "status": "completed",
                "message": f"{label} API ok (token: {token[:12]}...)",
            })
        except Exception as e:
            result["success"] = False
            result["error"] = f"API call failed: {e}"
            stream_writer({
                "step": f"[{label}] Call API",
                "status": "failed",
                "message": str(e),
            })
            return {"tech_results": [result]}

        # Step 3: Poll
        poll_interval = 10
        max_polls = 1000
        count = 0
        try:
            for count in range(1, max_polls + 1):
                if count > 1:
                    await asyncio.sleep(poll_interval)
                
                run_code, status, work_item = await check_coverage_status(token)
                if work_item:
                    if run_code == 1:
                        stream_writer({
                            "step": f"[{label}] Poll",
                            "status": "completed",
                            "message": f"Poll #{count}: {label} done!",
                        })
                        result["success"] = True
                        result["poll_count"] = count
                        return {"tech_results": [result]}
                    elif run_code == 0:
                        stream_writer({
                            "step": f"[{label}] Poll",
                            "status": "in_progress",
                            "message": f"Poll #{count}: {label} — {str(status).strip()}",
                        })
                        continue
                    elif run_code == 2:
                        raise Exception(f"Coverage Generation failed in CWE : {status}")
                else:
                    stream_writer({
                        "step": f"[{label}] Poll",
                        "status": "in_progress",
                        "message": f"Poll #{count}: {label} — {status}",
                    })
                    continue

            raise Exception("Polling timed out")
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["poll_count"] = count
            stream_writer({
                "step": f"[{label}] Poll",
                "status": "failed",
                "message": str(e),
        })
        return {"tech_results": [result]}
