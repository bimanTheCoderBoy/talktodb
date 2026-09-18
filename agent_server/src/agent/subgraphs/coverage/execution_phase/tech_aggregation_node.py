import logging

from langgraph.types import Command
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter

from agent.utils.state import State, TechExecution
from agent.subgraphs.coverage.utils.utils import update_last_tool_message_of_master_graph

logger = logging.getLogger(__name__)


def coverage_tech_aggregation(state: State):
    """
    Runs after all Send branches of coverage_run_tech_pipeline complete.

    * Reads tech_results (reducer-collected list of dicts).
    * Builds TechExecution objects and stores them on coverage_state.lte / .nr.
    * If at least one tech succeeded  → fans out to Phase 3 (map + reports).
    * If all failed                    → routes back to master_agent_node with error.
    """
    stream_writer: StreamWriter = get_stream_writer()

    lte_result = None
    nr_result = None
    for r in state.tech_results:
        tech = r.get("tech")
        if tech == "lte":
            lte_result = r
        elif tech == "nr":
            nr_result = r

    lte_exec = (
        TechExecution(**{k: v for k, v in lte_result.items() if k != "tech"})
        if lte_result else None
    )
    nr_exec = (
        TechExecution(**{k: v for k, v in nr_result.items() if k != "tech"})
        if nr_result else None
    )

    any_success = (lte_exec and lte_exec.success) or (nr_exec and nr_exec.success)

    if lte_exec and lte_exec.success:
        stream_writer({
            "step": "[LTE] Result",
            "status": "completed",
            "message": "LTE coverage completed successfully",
        })
    elif lte_exec and lte_exec.error:
        stream_writer({
            "step": "[LTE] Result",
            "status": "failed",
            "message": f"LTE failed: {lte_exec.error}",
        })

    if nr_exec and nr_exec.success:
        stream_writer({
            "step": "[NR] Result",
            "status": "completed",
            "message": "NR coverage completed successfully",
        })
    elif nr_exec and nr_exec.error:
        stream_writer({
            "step": "[NR] Result",
            "status": "failed",
            "message": f"NR failed: {nr_exec.error}",
        })

    cs = state.coverage_state
    state_update = {
        "coverage_state": {
            **cs.model_dump(),
            "lte": lte_exec.model_dump() if lte_exec else None,
            "nr": nr_exec.model_dump() if nr_exec else None,
        },
    }

    if not any_success:
        errors = []
        if lte_exec and lte_exec.error:
            errors.append(f"LTE: {lte_exec.error}")
        if nr_exec and nr_exec.error:
            errors.append(f"NR: {nr_exec.error}")
        error_msg = "All coverage branches failed. " + "; ".join(errors)
        stream_writer({
            "step": "Tech Aggregation",
            "status": "failed",
            "message": error_msg,
        })
        updated = update_last_tool_message_of_master_graph(
            state.main_message_context, error_msg,
        ) or state.main_message_context
        state_update["main_message_context"] = updated
        return Command(update=state_update, goto="master_agent_node")

    stream_writer({
        "step": "Tech Aggregation",
        "status": "completed",
        "message": "Coverage API runs complete — generating reports and loading map...",
    })

    return [
        Command(update=state_update, goto="coverage_map_viewer_node"),
        Command(goto="coverage_generate_reports_node"),
    ]
