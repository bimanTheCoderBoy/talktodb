import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from PIL import Image

from fastapi import HTTPException
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from asp_app.config.acss_config import (
    ACSSConfig,
    CoverageAPIConfig,
    get_acss_config,
    get_coverage_api_config,
    join_paths,
)
from asp_app.config.array_type_mapper import ArrayTypeMapper
from asp_app.db.models import ACSSSession, ACSSStep, StepName, StepStatus
from asp_app.db.schemas.execution import ExecutionStepName, ExecutionStatus
from asp_app.services.redis_service import RedisService
from asp_app.services.run_coverage_service import RunCoverageService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _path_for_bil_retrieval(path: str) -> str:
    """Format *path* for BIL file retrieval.  OS-aware:

    * **Windows** → UNC format (``\\\\host\\path\\parts``)
    * **Linux / Docker** → forward-slash Linux path (``/host/path/parts``)
    """
    if not path or not path.strip():
        return path
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return path
    parts = [p for p in normalized.split("/") if p]
    if not parts:
        return path
    if os.name == "nt":
        return "\\\\" + "\\".join(parts)
    return "/" + "/".join(parts)


# ---------------------------------------------------------------------------
# BIL discovery
# ---------------------------------------------------------------------------

async def _find_bil_files(root_dir: str) -> List[str]:
    """Recursively find all ``.bil`` files under *root_dir*.

    Returns a list of paths.  Runs in a thread pool so it
    never blocks the event loop.
    """

    def _walk():
        bil_files: List[str] = []
        if not os.path.isdir(root_dir):
            logger.warning("_find_bil_files: directory does not exist: %s", root_dir)
            return bil_files
        for subdir, _, files in os.walk(root_dir):
            for fname in files:
                if fname.lower().endswith(".bil"):
                    bil_files.append(os.path.join(subdir, fname))
        return bil_files

    return await asyncio.to_thread(_walk)


# ---------------------------------------------------------------------------
# BIL → PNG + JSON converter  (adapted from backend bil_to_png.py)
# ---------------------------------------------------------------------------

def _convert_bil_to_rgb_png(
    base_filename: str,
    output_dir: str,
    layer_prefix: str,
    array_type: str,
) -> Dict[str, Any]:
    """Convert a single ``.bil`` raster to a 24-bit RGB-encoded PNG with a
    companion ``.json`` metadata sidecar.

    Parameters
    ----------
    base_filename : str
        Full path to the BIL **without** the ``.bil`` extension.
    output_dir : str
        Directory where ``.png`` and ``.json`` will be written.
    epsg : str
        EPSG code stored in the metadata JSON.
    layer_prefix : str
        Prefix prepended to the output file name (e.g. ``"baseline"`` or
        ``"updated"``).
    array_type : str
        Array type label (e.g. ``"LTE_Best_RSRP"``).

    Returns
    -------
    dict
        ``{"success": True, "basename": "<name>"}`` on success, or
        ``{"success": False, "error": "<msg>"}`` on failure.
    """
    input_bil = f"{base_filename}.bil"
    input_hdr = f"{base_filename}.hdr"

    file_basename = os.path.basename(base_filename)
    output_name = f"{layer_prefix}_{array_type}_{file_basename}"

    output_png = os.path.join(output_dir, f"{output_name}.png")
    output_json = os.path.join(output_dir, f"{output_name}.json")

    # --- Validation ---
    if not os.path.exists(input_bil):
        return {"success": False, "error": f".bil file not found: {input_bil}"}
    if not os.path.exists(input_hdr):
        return {"success": False, "error": f".hdr file not found: {input_hdr}"}

    try:
        with rasterio.open(input_bil) as src:
            data = src.read(1)
            width = src.width
            height = src.height
            bounds = src.bounds
            detected_epsg = src.crs.to_epsg() 
            nodata_val = src.nodata
            if nodata_val is None:
                nodata_val = -9999.0
    except RasterioIOError as e:
        return {"success": False, "error": f"Rasterio could not open the file: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error while reading: {e}"}

    # --- Filter valid data ---
    valid_mask = (data != nodata_val) & (~np.isnan(data)) & (~np.isinf(data))
    if not np.any(valid_mask):
        return {"success": False, "error": f"File {input_bil} contains only NoData ({nodata_val}) or NaNs"}

    data_min = float(data[valid_mask].min())
    data_max = float(data[valid_mask].max())

    if data_max == data_min:
        data_max = data_min + 1.0

    # --- Normalize and encode to 24-bit RGB ---
    normalized = np.zeros_like(data, dtype=np.float64)
    normalized[valid_mask] = (data[valid_mask] - data_min) / (data_max - data_min)
    normalized[~valid_mask] = 0.0

    int24 = (normalized * 16777215).astype(np.uint32)
    r = (int24 >> 16) & 0xFF
    g = (int24 >> 8) & 0xFF
    b = int24 & 0xFF
    rgb_image = np.stack([r, g, b], axis=-1).astype(np.uint8)

    # --- Save PNG ---
    try:
        Image.fromarray(rgb_image).save(output_png)
    except Exception as e:
        return {"success": False, "error": f"Failed to save PNG: {e}"}

    # --- Save metadata JSON ---
    meta = {
        "name": output_name,
        "epsg": str(detected_epsg),
        "bounds": {
            "west": bounds.left,
            "south": bounds.bottom,
            "east": bounds.right,
            "north": bounds.top,
        },
        "valueMin": data_min,
        "valueMax": data_max,
        "type": ArrayTypeMapper.to_frontend_type(array_type),
    }
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4)
    except Exception as e:
        return {"success": False, "error": f"Failed to save JSON metadata: {e}"}

    return {"success": True, "basename": output_name}


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class MapEncodingService:
    """Converts BIL coverage outputs into PNG + manifest + cells.json for the
    interactive 2-D map viewer."""

    @staticmethod
    async def run(
        db: AsyncSession,
        session: ACSSSession,
        step: ACSSStep,
        session_id: UUID,
        job_id: str,
        redis_client: Redis,
        project_name: str,
    ) -> ACSSStep:
        """Main entry point – called from ``ExecutionService.run_execution``.

        1. Locate baseline and updated (baseline+candidates) BIL directories.
        2. Convert every ``.bil`` in each to an encoded PNG + JSON sidecar.
        3. Write ``manifest.json`` and ``cells.json``.
        4. Persist output paths in ``step.step_metadata``.
        """
        step.status = StepStatus.IN_PROGRESS
        flag_modified(step, "status")
        await db.commit()

        await RunCoverageService._update_execution_state(
            db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
            ExecutionStatus.RUNNING, 0, job_id, redis_client,
        )

        try:
            # ---- Config ----
            acss_config: ACSSConfig = get_acss_config()
            cov_config: CoverageAPIConfig = get_coverage_api_config()

            polygon_state = session.setup_state.get("polygon", {})
            array_type = polygon_state.get("arrayType", "LTE_Best_RSRP")

            # ---- Resolve BIL directories (use retrieval root, convert to UNC on Windows) ----
            baseline_bil_dir = _path_for_bil_retrieval(
                join_paths(
                    cov_config.coverage_root_output_retrieval_location,
                    project_name,
                    str(session_id),
                    StepName.BASELINE_COVERAGE.value,
                    array_type,
                )
            )
            updated_bil_dir = _path_for_bil_retrieval(
                join_paths(
                    cov_config.coverage_root_output_retrieval_location,
                    project_name,
                    str(session_id),
                    StepName.RUNNING_COVERAGE_FOR_BASELINE_AND_CANDIDATES.value,
                    array_type,
                )
            )

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Baseline BIL dir: {baseline_bil_dir}",
            )
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Updated BIL dir: {updated_bil_dir}",
            )

            # ---- Prepare output directory ----
            output_dir = os.path.join(acss_config.acss_map_encoded_dir, project_name, str(session_id))
            if os.name == "nt":
                output_dir = os.path.abspath(output_dir)
            await asyncio.to_thread(os.makedirs, output_dir, exist_ok=True)

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Output dir: {output_dir}",
            )

            # ---- Discover BIL files ----
            baseline_bils = await _find_bil_files(baseline_bil_dir)
            updated_bils = await _find_bil_files(updated_bil_dir)

            total_files = len(baseline_bils) + len(updated_bils)
            if total_files == 0:
                await RedisService.publish_log(
                    redis_client, f"logs:{session_id}",
                    "No BIL files found in baseline or updated directories",
                )
                raise HTTPException(
                    status_code=400,
                    detail="No BIL files found for map encoding",
                )

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Found {len(baseline_bils)} baseline + {len(updated_bils)} updated BIL files",
            )

            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                ExecutionStatus.RUNNING, 10, job_id, redis_client,
            )

            # ---- Convert BILs to PNG + JSON ----
            successful: List[str] = []
            failed: List[Dict[str, Any]] = []
            processed = 0

            # Helper to process a batch of BILs with a given prefix
            async def _process_batch(bil_paths: List[str], prefix: str):
                nonlocal processed
                for bil_path in bil_paths:
                    processed += 1
                    base_filename = bil_path[:-4] if bil_path.lower().endswith(".bil") else bil_path

                    await RedisService.publish_log(
                        redis_client, f"logs:{session_id}",
                        f"Converting [{processed}/{total_files}]: {os.path.basename(bil_path)} ({prefix})",
                    )

                    result = await asyncio.to_thread(
                        _convert_bil_to_rgb_png,
                        base_filename, output_dir, prefix, array_type,
                    )

                    if result.get("success"):
                        successful.append(result["basename"])
                    else:
                        failed.append({
                            "file": os.path.basename(bil_path),
                            "prefix": prefix,
                            "error": result.get("error", "Unknown error"),
                        })

                    # Update progress (10–80% range for conversion)
                    pct = 10 + int((processed / total_files) * 70)
                    await RunCoverageService._update_execution_state(
                        db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                        ExecutionStatus.RUNNING, min(pct, 80), job_id, redis_client,
                    )

            await _process_batch(baseline_bils, "baseline")
            await _process_batch(updated_bils, "updated")

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"BIL conversion done. Success: {len(successful)}, Failed: {len(failed)}",
            )

            # ---- Write manifest.json ----
            manifest = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "files": successful,
                "total_files": len(successful),
                "failed_count": len(failed),
            }
            if failed:
                manifest["failed_files"] = failed

            manifest_path = os.path.join(output_dir, "manifest.json")

            def _write_manifest():
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=4)

            await asyncio.to_thread(_write_manifest)
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"manifest.json written with {len(successful)} layers",
            )

            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                ExecutionStatus.RUNNING, 85, job_id, redis_client,
            )

            # ---- Write cells.json (baselineCells + savedCandidates) ----
            cells_json_path = os.path.join(output_dir, "cells.json")
            cells_data = _build_cells_json(session)

            def _write_cells():
                with open(cells_json_path, "w", encoding="utf-8") as f:
                    json.dump(cells_data, f, indent=4)

            await asyncio.to_thread(_write_cells)
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"cells.json written with {len(cells_data)} sites",
            )

            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                ExecutionStatus.RUNNING, 95, job_id, redis_client,
            )

            # ---- Persist metadata on the step ----
            step.step_metadata = {
                "output_dir": output_dir,
                "manifest_path": manifest_path,
                "cells_json_path": cells_json_path,
                "total_converted": len(successful),
                "total_failed": len(failed),
                "total_cells_sites": len(cells_data),
                "baseline_bil_dir": baseline_bil_dir,
                "updated_bil_dir": updated_bil_dir,
            }
            step.status = StepStatus.COMPLETED
            flag_modified(step, "step_metadata")
            flag_modified(step, "status")

            setup_state = dict(session.setup_state or {})
            setup_state["mapEncodedOutputDir"] = output_dir
            session.setup_state = setup_state
            flag_modified(session, "setup_state")

            await db.commit()

            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                ExecutionStatus.DONE, 100, job_id, redis_client, end_time=True,
            )

            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Map encoding complete. {len(successful)} layers encoded to {output_dir}",
            )

            return step

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            error_msg = str(e)
            step.status = StepStatus.FAILED
            step.step_metadata = (step.step_metadata or {}) | {"error_message": error_msg}
            flag_modified(step, "status")
            flag_modified(step, "step_metadata")
            await db.commit()
            await RunCoverageService._update_execution_state(
                db, session, ExecutionStepName.CONVERTING_BILS_FOR_INTERACTIVE_VIEW,
                ExecutionStatus.ERROR, 99, job_id, redis_client, end_time=True,
            )
            await RedisService.publish_log(
                redis_client, f"logs:{session_id}",
                f"Map encoding error: {error_msg}",
            )
            raise HTTPException(
                status_code=400,
                detail=f"Map encoding failed: {error_msg}",
            ) from e


# ---------------------------------------------------------------------------
# cells.json builder
# ---------------------------------------------------------------------------

def _build_cells_json(session: ACSSSession) -> List[Dict[str, Any]]:
    """Build a combined site list from baselineCells + savedCandidates.

    The output format matches what the frontend ``CellsLayer`` component
    expects::

        [
            {
                "site_iid": "…",
                "longitude": 12.34,
                "latitude": 56.78,
                "is_candidate": false,
                "cells": [
                    {"cell_iid": "…", "azimuth": 120, "band": "700", …},
                    …
                ]
            },
            …
        ]

    ``is_candidate`` is True for sites that came from ASP savedCandidates
    (newly added). The coverage map viewer uses this to render those site
    markers in green so they are distinguishable from baseline (red) in
    Extended / split Updated Coverage view.
    """
    setup = session.setup_state or {}
    polygon = setup.get("polygon", {})
    baseline_sites: List[Dict[str, Any]] = polygon.get("baselineCells", [])
    saved_candidates: List[Dict[str, Any]] = setup.get("savedCandidates", [])

    # Use a dict keyed by site_iid to merge / deduplicate
    sites_map: Dict[str, Dict[str, Any]] = {}

    for site in baseline_sites:
        site_iid = site.get("site_iid") or site.get("siteIid") or ""
        if not site_iid:
            continue
        sites_map[site_iid] = {
            "site_iid": site_iid,
            "longitude": site.get("longitude"),
            "latitude": site.get("latitude"),
            "is_candidate": False,
            "cells": list(site.get("cells", [])),
        }

    for site in saved_candidates:
        site_iid = site.get("site_iid") or site.get("siteIid") or ""
        if not site_iid:
            continue
        if site_iid in sites_map:
            # Merge cells, avoiding duplicates by cell_iid.
            # Mark the site as candidate so ASP-added sites stay green even
            # when they share a site_iid with baseline.
            sites_map[site_iid]["is_candidate"] = True
            existing_iids = {
                c.get("cell_iid") for c in sites_map[site_iid]["cells"]
            }
            for cell in site.get("cells", []):
                if cell.get("cell_iid") not in existing_iids:
                    sites_map[site_iid]["cells"].append(cell)
                    existing_iids.add(cell.get("cell_iid"))
        else:
            sites_map[site_iid] = {
                "site_iid": site_iid,
                "longitude": site.get("longitude"),
                "latitude": site.get("latitude"),
                "is_candidate": True,
                "cells": list(site.get("cells", [])),
            }

    return list(sites_map.values())
