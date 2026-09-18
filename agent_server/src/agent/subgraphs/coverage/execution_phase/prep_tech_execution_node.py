import logging

from langgraph.types import Command
from langgraph.config import get_stream_writer
from langgraph.types import StreamWriter
from langgraph.runtime import Runtime

from agent.utils.state import State, TechExecution, CoverageUrlConfig, ctx_schema_State
from agent.utils.database import segregate_iids_by_technology
from agent.subgraphs.coverage.utils.utils import update_last_tool_message_of_master_graph

logger = logging.getLogger(__name__)


async def coverage_prep_tech_execution(state: State, runtime: Runtime[ctx_schema_State]) -> Command:
    """
    Validate the interrupt result and build TechExecution objects for
    each active technology (LTE / NR).

    Routes to coverage_fan_out_passthrough when at least one tech is
    ready, or back to master_agent_node on rejection / no-tech.
    """
    stream_writer: StreamWriter = get_stream_writer()
    cs = state.coverage_state

    if not cs.user_approved:
        stream_writer({
            "step": "Prep Tech Execution",
            "status": "skipped",
            "message": "User did not approve — returning to master agent.",
        })
        updated = update_last_tool_message_of_master_graph(
            state.main_message_context,
            "Coverage run cancelled: user did not approve the map data.",
        ) or state.main_message_context
        return Command(
            update={"main_message_context": updated},
            goto="master_agent_node",
        )

    params = cs.parameters or {}
    output = cs.output or {}
    url_settings = cs.url_parameter_settings or {}

    user_email = runtime.context.user_email
    iids_by_tech = await segregate_iids_by_technology(
        state.project_name, cs.iids or [], user_email,
    )

    lte_exec = None
    nr_exec = None

    for tech_key in ("lte", "nr"):
        tech_params = params.get(tech_key)
        if tech_params is None:
            logger.info(f"Skipping {tech_key}: no parameters selected")
            continue

        selected = [
            at.value
            for at in tech_params.arrayTypes
            if at.isSelected
        ]
        if not selected:
            logger.info(f"Skipping {tech_key}: no array types selected")
            continue

        tech_out = output.get(tech_key)
        tech_url = url_settings.get(tech_key)
        tech_iids = iids_by_tech.get(tech_key, [])
        if not tech_iids:
            logger.info(f"Skipping {tech_key}: no cells of this technology in selection")
            continue

        exec_obj = TechExecution(
            iids=tech_iids,
            array_types=selected,
            output_path=tech_out.path if tech_out else "",
            output_name=tech_out.name if tech_out else "",
            url_config=tech_url if tech_url else CoverageUrlConfig(),
        )

        if tech_key == "lte":
            lte_exec = exec_obj
        else:
            nr_exec = exec_obj

    if lte_exec is None and nr_exec is None:
        error_msg = (
            "No technology has selected array types. "
            "Please select at least one array type for LTE or NR."
        )
        stream_writer({
            "step": "Prep Tech Execution",
            "status": "failed",
            "message": error_msg,
        })
        updated = update_last_tool_message_of_master_graph(
            state.main_message_context, error_msg,
        ) or state.main_message_context
        return Command(
            update={"main_message_context": updated},
            goto="master_agent_node",
        )

    techs = []
    if lte_exec:
        techs.append(f"LTE ({len(lte_exec.array_types)} array types)")
    if nr_exec:
        techs.append(f"NR ({len(nr_exec.array_types)} array types)")
    stream_writer({
        "step": "Prep Tech Execution",
        "status": "completed",
        "message": f"Prepared execution for: {', '.join(techs)}",
    })

    return Command(
        update={
            "coverage_state": {
                **cs.model_dump(),
                "lte": lte_exec.model_dump() if lte_exec else None,
                "nr": nr_exec.model_dump() if nr_exec else None,
            },
        },
        goto="coverage_fan_out_passthrough",
    )
