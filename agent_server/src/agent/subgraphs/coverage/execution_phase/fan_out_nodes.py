import logging

from langgraph.types import Send

from agent.utils.state import State

logger = logging.getLogger(__name__)


def coverage_fan_out_passthrough(state: State):
    """No-op node. Exists solely as an anchor for the conditional Send edge."""
    return {}


def coverage_fan_out_by_tech(state: State):
    """
    Conditional-edge function attached to coverage_fan_out_passthrough.

    Returns a list of Send objects — one per active technology whose
    TechExecution was populated by the prep node.
    """
    cs = state.coverage_state
    sends = []

    for tech_key in ("lte", "nr"):
        tech_exec = getattr(cs, tech_key, None)
        if tech_exec is None or not tech_exec.array_types:
            continue

        sends.append(Send("coverage_run_tech_pipeline", {
            "tech": tech_key,
            "iids": tech_exec.iids or cs.iids or [],
            "array_types": tech_exec.array_types,
            "output_path": tech_exec.output_path or "",
            "output_name": tech_exec.output_name or "",
            "url_config": tech_exec.url_config.model_dump() if tech_exec.url_config else {},
            "boundaries": cs.boundaries,
            "project_name": state.project_name,
            "user_email": state.user_email or "",
        }))

    if not sends:
        logger.warning("coverage_fan_out_by_tech: no techs to run — fallback to master")
        return "master_agent_node"

    return sends
