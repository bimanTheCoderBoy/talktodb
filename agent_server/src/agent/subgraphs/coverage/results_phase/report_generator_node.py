import asyncio
import os
from pathlib import Path
from typing import Dict, Any, List

from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

from agent.config.coverage_config import (
    CoverageAPIConfig,
    CoverageReportConfig,
    join_paths,
    path_for_bil_retrieval,
)
from agent.utils.state import State, ctx_schema_State
from agent.subgraphs.coverage.utils.coverage_report import process_all_files
from agent.subgraphs.coverage.utils.get_outer_polygon_from_user_db import (
    get_outer_polygon_from_user_db,
)


async def coverage_generate_reports_node(
    state: State,
    runtime: Runtime[ctx_schema_State],
) -> Dict[str, Any]:
    """
    Generate RSRP coverage CSV reports by intersecting BIL raster data
    with polygon boundaries.  Writes ONLY to ``coverage_report_result``
    — no ``messages`` updates (the join node handles that).
    """
    try:
        stream_writer: StreamWriter = get_stream_writer()
        stream_writer({"step": "Report Gen", "status": "started", "message": "Processing BIL files to generate coverage reports..."})

        cs = state.coverage_state
        tech_branches = [(cs.lte, "LTE"), (cs.nr, "NR")]
        has_tech_branches = any(t is not None and t.success for t, _ in tech_branches)

        if not has_tech_branches:
            raise ValueError("No successful technology executions found. Cannot generate reports.")

        api_config = CoverageAPIConfig()
        report_config = CoverageReportConfig()

        # Resolve polygon boundaries
        boundaries = cs.boundaries
        if boundaries is None:
            stream_writer({"step": "Report Gen", "status": "in_progress", "message": "No user polygon — fetching project config polygon from DB..."})
            boundaries = await get_outer_polygon_from_user_db(
                runtime.context.user_email, runtime.context.project_name,
            )
            if not boundaries:
                raise ValueError("No polygon boundaries available. Neither user-drawn polygon nor project config polygon found.")

        report_folder = report_config.report_folder_path
        if not report_folder:
            raise ValueError("COVERAGE_REPORT_FOLDER_PATH environment variable is not set")

        # Build per-tech report tasks so we can tag results by tech label
        all_array_types: List[str] = []
        report_tasks: list = []
        task_tech_labels: List[str] = []

        for tech_exec, tech_label in tech_branches:
            if tech_exec is None or not tech_exec.success:
                continue
            t_output_path = tech_exec.output_path or api_config.payload_default_output_location
            t_output_name = tech_exec.output_name or api_config.payload_output_name
            t_array_types = tech_exec.array_types or []
            all_array_types.extend(t_array_types)
            bil_root = join_paths(api_config.bil_file_root_retrieval_path, t_output_path)
            for at in t_array_types:
                bil_folder = str(Path(bil_root) / t_output_name / at)
                bil_folder = path_for_bil_retrieval(bil_folder)
                stream_writer({"step": "Report Gen", "status": "in_progress", "message": f"Queuing report for [{tech_label}] {at}"})
                report_tasks.append(process_all_files(bil_folder, report_folder, boundaries))
                task_tech_labels.append(tech_label)

        stream_writer({"step": "Report Gen", "status": "in_progress", "message": f"Processing {len(report_tasks)} array type(s) in parallel..."})
        all_results = await asyncio.gather(*report_tasks, return_exceptions=True)

        created_files: List[str] = []
        created_files_by_tech: Dict[str, List[str]] = {}
        all_skipped_reasons: List[str] = []

        for idx, r in enumerate(all_results):
            tech_label = task_tech_labels[idx]
            if isinstance(r, Exception):
                print(f"[{tech_label}] Array type processing failed: {r}")
                continue
            files = r.get("created_files", [])
            created_files.extend(files)
            created_files_by_tech.setdefault(tech_label, []).extend(files)
            all_skipped_reasons.extend(r.get("skipped_reasons", []))

        abs_report_folder = os.path.abspath(report_folder)

        stream_writer({
            "step": "Report Gen",
            "status": "completed" if created_files else "failed",
            "message": f"Reports: {len(created_files)} created, {len(all_skipped_reasons)} skipped",
        })

        if created_files:
            return {
                "coverage_report_result": {
                    "success": True,
                    "status": "completed",
                    "array_types": all_array_types,
                    "created_files": created_files,
                    "created_files_by_tech": created_files_by_tech,
                    "skipped_reasons": all_skipped_reasons,
                    "report_folder": abs_report_folder,
                },
            }
        else:
            skipped_text = ""
            if all_skipped_reasons:
                skipped_text = " Skipped: " + "; ".join(all_skipped_reasons)
            return {
                "coverage_report_result": {
                    "success": False,
                    "status": "completed_with_no_reports",
                    "array_types": all_array_types,
                    "created_files": [],
                    "created_files_by_tech": {},
                    "skipped_reasons": all_skipped_reasons,
                    "report_folder": abs_report_folder,
                    "error": f"No reports generated.{skipped_text} Check if BIL files exist.",
                },
            }

    except Exception as e:
        error_content = f"Error during report generation: {e}"
        stream_writer({"step": "Report Gen", "status": "failed", "message": error_content})
        return {
            "coverage_report_result": {
                "success": False,
                "status": "failed",
                "error": error_content,
            },
        }
