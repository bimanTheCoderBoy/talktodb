import asyncio
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

from agent.config.coverage_config import (
    COVERAGE_PNG_ENCODING_PATH,
    MAX_COVERAGE_PNG_VALIDITY_IN_DAYS,
    CoverageAPIConfig,
    join_paths,
    path_for_bil_retrieval,
)
from agent.utils.state import State, ctx_schema_State
from agent.utils.database import get_coverage_map_data_structure_from_iids_only_iid_cells
from agent.subgraphs.coverage.utils.bil_to_png import convert_bil_to_rgb_png


async def _cleanup_old_png_folders(base_path: str, max_age_days: int) -> Dict[str, Any]:
    """Remove timestamped folders older than *max_age_days*."""

    def _cleanup():
        if not os.path.exists(base_path):
            return {"removed": 0, "errors": [], "skipped": 0}

        removed_count = 0
        error_list: list = []
        skipped_count = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        try:
            for folder_name in os.listdir(base_path):
                folder_path = os.path.join(base_path, folder_name)
                if not os.path.isdir(folder_path):
                    continue
                try:
                    folder_date = datetime.strptime(folder_name, "%Y%m%d_%H%M%S")
                    if folder_date < cutoff_date:
                        shutil.rmtree(folder_path)
                        removed_count += 1
                except ValueError:
                    skipped_count += 1
                    continue
                except Exception as e:
                    error_list.append({"folder": folder_name, "error": str(e)})
        except Exception as e:
            error_list.append({"folder": base_path, "error": str(e)})

        return {"removed": removed_count, "errors": error_list, "skipped": skipped_count}

    return await asyncio.to_thread(_cleanup)


async def _find_bil_files(root_dir: str) -> List[str]:
    """Recursively find all .bil files under *root_dir*."""

    def _find():
        bil_files: list[str] = []
        for subdir, _, files in os.walk(root_dir):
            for file in files:
                if file.lower().endswith(".bil"):
                    bil_files.append(os.path.join(subdir, file))
        return bil_files

    return await asyncio.to_thread(_find)


# ── Main node ────────────────────────────────────────────────────────

async def coverage_map_viewer_node(state: State, runtime: Runtime[ctx_schema_State]):
    """
    Convert BIL raster files into RGB-encoded PNGs, generate cells.json
    and manifest.json.  Writes ONLY to ``coverage_map_result`` — no
    ``messages`` updates (the join node handles that).
    """
    coverage_api_config = CoverageAPIConfig()
    stream_writer: StreamWriter = get_stream_writer()

    try:
        stream_writer({"step": "Map Viewer", "status": "in_progress", "message": "Collecting BIL paths from tech executions..."})
        cs = state.coverage_state
        tech_branches = [(cs.lte, "LTE"), (cs.nr, "NR")]
        has_tech_branches = any(t is not None and t.success for t, _ in tech_branches)

        if not has_tech_branches:
            raise ValueError("No successful technology executions found. Cannot build map data.")

        bil_files_map: Dict[str, List[str]] = {}
        for tech_exec, tech_label in tech_branches:
            if tech_exec is None or not tech_exec.success:
                continue
            t_output_path = tech_exec.output_path or coverage_api_config.payload_default_output_location
            t_output_name = tech_exec.output_name or coverage_api_config.payload_output_name
            t_array_types = tech_exec.array_types or []
            bil_root = join_paths(coverage_api_config.bil_file_root_retrieval_path, t_output_path)
            bil_root = path_for_bil_retrieval(bil_root)
            for at in t_array_types:
                bil_folder = str(Path(bil_root) / t_output_name / at)
                bil_file_paths = await _find_bil_files(bil_folder)
                bil_files_map.setdefault(at, []).extend(bil_file_paths)

        total_bil = sum(len(v) for v in bil_files_map.values())
        stream_writer({"step": "Map Viewer", "status": "in_progress", "message": f"Found {len(bil_files_map)} array types, {total_bil} BIL files"})

        if not COVERAGE_PNG_ENCODING_PATH:
            raise ValueError("COVERAGE_PNG_ENCODING_PATH environment variable is not set")

        # Cleanup old PNG folders
        stream_writer({"step": "Map Viewer Cleanup", "status": "in_progress", "message": f"Cleaning folders older than {MAX_COVERAGE_PNG_VALIDITY_IN_DAYS} days..."})
        cleanup_result = await _cleanup_old_png_folders(COVERAGE_PNG_ENCODING_PATH, MAX_COVERAGE_PNG_VALIDITY_IN_DAYS)
        stream_writer({"step": "Map Viewer Cleanup", "status": "in_progress", "message": f"Removed {cleanup_result['removed']} old folders."})

        # Create timestamped output folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = os.path.join(COVERAGE_PNG_ENCODING_PATH, timestamp)
        await asyncio.to_thread(os.makedirs, output_folder, exist_ok=True)

        # ── Generate cells.json ──────────────────────────────────────
        cells_json_error: str | None = None
        try:
            stream_writer({"step": "Generating cells.json", "status": "in_progress", "message": "Fetching cell data from database..."})
            project_name = state.project_name
            iids = cs.iids or []
            user_email = runtime.context.user_email

            if not project_name:
                raise ValueError("project_name is not set in state")
            if not iids:
                raise ValueError("No IIDs found in coverage_state")

            cells_data = await get_coverage_map_data_structure_from_iids_only_iid_cells(project_name, iids, user_email)
            cells_json_path = os.path.join(output_folder, "cells.json")

            def _write():
                with open(cells_json_path, "w") as f:
                    json.dump(cells_data, f, indent=4)

            await asyncio.to_thread(_write)
            stream_writer({"step": "Generating cells.json", "status": "completed", "message": f"cells.json generated with {len(cells_data)} sites"})
        except Exception as cells_error:
            cells_json_error = str(cells_error)
            stream_writer({"step": "Generating cells.json", "status": "failed", "message": f"Error: {cells_json_error}"})

        # ── Convert BIL → PNG (parallel) ─────────────────────────────
        stream_writer({"step": "BIL to PNG", "status": "in_progress", "message": "Starting conversion..."})

        successful_conversions: List[str] = []
        failed_conversions: List[Dict[str, Any]] = []
        array_type_files_map: Dict[str, List[str]] = {}

        total_files = sum(len(files) for files in bil_files_map.values())
        max_workers = max(1, min(total_files, 6))
        semaphore = asyncio.Semaphore(max_workers)

        async def _convert_one(bil_path: str, arr_type: str):
            base_filename = bil_path[:-4] if bil_path.lower().endswith(".bil") else bil_path
            async with semaphore:
                return arr_type, bil_path, await asyncio.to_thread(
                    convert_bil_to_rgb_png, base_filename, output_folder, array_type=arr_type,
                )

        tasks = []
        for array_type, bil_files in bil_files_map.items():
            array_type_files_map[array_type] = []
            for bil_path in bil_files:
                tasks.append(_convert_one(bil_path, array_type))

        stream_writer({"step": "BIL to PNG", "status": "in_progress", "message": f"Converting {total_files} file(s) (max {max_workers} workers)..."})
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                failed_conversions.append({"file": "unknown", "error": str(r)})
                continue
            arr_type, bil_path, result = r
            if result.get("success"):
                basename = result.get("basename", os.path.basename(bil_path))
                successful_conversions.append(basename)
                array_type_files_map[arr_type].append(basename)
            else:
                failed_conversions.append({
                    "file": os.path.basename(bil_path),
                    "error": result.get("error", "Unknown error"),
                })

        stream_writer({"step": "BIL to PNG", "status": "in_progress", "message": f"Done. Success: {len(successful_conversions)}, Failed: {len(failed_conversions)}"})

        # ── Generate manifest.json ───────────────────────────────────
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "files": successful_conversions,
            "array_types": array_type_files_map,
            "total_files": len(successful_conversions),
            "failed_count": len(failed_conversions),
        }
        if failed_conversions:
            manifest["failed_files"] = failed_conversions

        manifest_path = os.path.join(output_folder, "manifest.json")

        def _write_manifest():
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=4)

        await asyncio.to_thread(_write_manifest)

        absolute_output_path = os.path.abspath(output_folder)
        relative_path = absolute_output_path.split("teoco_data_store")[1] if "teoco_data_store" in absolute_output_path else ""
        map_link = f"/map/2d/teoco_data_store{relative_path}"

        stream_writer({"step": "Map Viewer", "status": "completed", "message": f"Processed {len(successful_conversions)} files. Map link: {map_link}"})

        return {
            "coverage_map_result": {
                "success": True,
                "status": "completed",
                "output_folder": absolute_output_path,
                "manifest_path": os.path.abspath(manifest_path),
                "map_link": map_link,
                "total_files_converted": len(successful_conversions),
                "failed_conversions": len(failed_conversions),
                "array_types_processed": list(array_type_files_map.keys()),
                "array_type_files_map": array_type_files_map,
                "cells_json_error": cells_json_error,
                "failed_files": failed_conversions,
            },
        }

    except Exception as e:
        error_content = f"Error: {e}"
        stream_writer({"step": "Map Viewer", "status": "failed", "message": error_content})
        return {
            "coverage_map_result": {
                "success": False,
                "status": "failed",
                "error": error_content,
            },
        }
