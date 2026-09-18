import json
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.types import Command
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

from agent.utils.state import State
from agent.subgraphs.coverage.utils.utils import update_last_tool_message_of_master_graph


def _build_summary(state: State, map_result: dict, report_result: dict) -> str:
    """Build a human-readable detailed summary of all Phase 3 results."""
    cs = state.coverage_state
    lines = ["Coverage Execution Summary", "=" * 26, ""]

    # ── Technologies ─────────────────────────────────────────────────
    lines.append("Technologies:")
    for tech_exec, label in [(cs.lte, "LTE"), (cs.nr, "NR")]:
        if tech_exec is None:
            continue
        if tech_exec.success:
            lines.append(f"  - {label}: success (poll count: {tech_exec.poll_count})")
        else:
            lines.append(f"  - {label}: failed (error: {tech_exec.error})")

    # ── Map Processing ───────────────────────────────────────────────
    lines.append("")
    lines.append("Map Processing:")
    map_success = bool(map_result.get("success"))
    lines.append(f"  - Status: {'success' if map_success else 'failed'}")
    if map_success:
        lines.append(f"  - Files converted: {map_result.get('total_files_converted', 0)}")
        lines.append(f"  - Failed conversions: {map_result.get('failed_conversions', 0)}")
        cells_err = map_result.get("cells_json_error")
        lines.append(f"  - cells.json: {'Failed - ' + cells_err if cells_err else 'Created successfully'}")
        lines.append(f"  - Map link: {map_result.get('map_link', 'N/A')}")
    else:
        lines.append(f"  - Error: {map_result.get('error', 'unknown')}")

    # ── Report Generation ────────────────────────────────────────────
    lines.append("")
    lines.append("Report Generation:")
    report_success = bool(report_result.get("success"))
    lines.append(f"  - Status: {'success' if report_success else 'failed'}")

    files_by_tech = report_result.get("created_files_by_tech", {})
    if files_by_tech:
        lines.append("  - Reports created:")
        for tech_label, files in files_by_tech.items():
            for f in files:
                lines.append(f"    [{tech_label}] {Path(f).name}")
    elif report_success:
        created = report_result.get("created_files", [])
        if created:
            lines.append("  - Reports created:")
            for f in created:
                lines.append(f"    {Path(f).name}")

    report_folder = report_result.get("report_folder")
    if report_folder:
        lines.append(f"  - Report folder: {report_folder}")

    skipped = report_result.get("skipped_reasons", [])
    if skipped:
        lines.append(f"  - Skipped: {len(skipped)}")
        for reason in skipped:
            lines.append(f"    - {reason}")

    if not report_success and report_result.get("error"):
        lines.append(f"  - Error: {report_result.get('error')}")

    # ── Errors ───────────────────────────────────────────────────────
    errors = []
    for tech_exec, label in [(cs.lte, "LTE"), (cs.nr, "NR")]:
        if tech_exec and not tech_exec.success and tech_exec.error:
            errors.append(f"  - {label}: {tech_exec.error}")
    if not map_success and map_result.get("error"):
        errors.append(f"  - Map: {map_result.get('error')}")
    if not report_success and report_result.get("error"):
        errors.append(f"  - Report: {report_result.get('error')}")

    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(errors)

    return "\n".join(lines)


async def coverage_results_join_node(state: State) -> Command:
    """
    Join node for the parallel map-viewer and report-generation branches.

    Responsibilities:
    1. Read coverage_map_result + coverage_report_result
    2. Build a detailed summary string
    3. Produce up to 3 AIMessages in ``messages``:
       - GO_TO_MAP_LINK  (map link for frontend navigation)
       - coverage_summary (detailed text for the user)
    4. Write the same summary into main_message_context via
       update_last_tool_message_of_master_graph
    5. Reset transient coverage state fields
    6. Route to master_agent_node
    """
    stream_writer: StreamWriter = get_stream_writer()

    map_result = state.coverage_map_result or {
        "success": False, "status": "missing", "error": "Map result missing.",
    }
    report_result = state.coverage_report_result or {
        "success": False, "status": "missing", "error": "Report result missing.",
    }

    # ── Build detailed summary ───────────────────────────────────────
    summary = _build_summary(state, map_result, report_result)

    # ── Construct UI messages ────────────────────────────────────────
    ui_messages = []

    map_link = map_result.get("map_link")
    if map_result.get("success") and map_link:
        ui_messages.append(AIMessage(name="GO_TO_MAP_LINK", content=map_link))

    ui_messages.append(AIMessage(name="coverage_summary", content=summary))

    # ── Update main_message_context for master agent ─────────────────
    updated_context = update_last_tool_message_of_master_graph(
        state.main_message_context, summary,
    ) or state.main_message_context

    stream_writer({
        "step": "Results Join",
        "status": "completed",
        "message": (
            f"Map: {'ok' if map_result.get('success') else 'fail'}, "
            f"Reports: {len(report_result.get('created_files', []) or [])}"
        ),
    })

    cs = state.coverage_state
    return Command(
        update={
            "messages": ui_messages,
            "main_message_context": updated_context,
            "coverage_state": {
                **cs.model_dump(),
                "iids": None,
                "lte": None,
                "nr": None,
            },
            "coverage_map_result": None,
            "coverage_report_result": None,
            "coverage_message_context_clean_flag": True,
            "coverage_message_context": state.coverage_message_context + [AIMessage(name="coverage_summary", content=summary)],
        },  
        goto="__end__",
    )
