from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

from computer.config.logger import get_computer_logger
from computer.state import AgentState, ctx_schema_State
from computer.utils.tool_call_utils import (
    partition_tool_calls,
    pending_tool_calls,
    tool_call_id,
    tool_call_name,
)
from computer.utils.tool_result_format import (
    format_llm_tool_result,
    format_ui_tool_result,
    truncate_tool_result_for_llm,
)

logger = get_computer_logger(__name__)

_FRONTEND_NOT_WIRED_JSON = (
    '{"success": false, "error": "Frontend tool execution is not wired yet (interrupt/resume pending)."}'
)


async def frontend_tool_runner(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """Runner for frontend tools (interrupt/resume wiring added in a later step)."""

    pending = pending_tool_calls(state)
    _, frontend_tool_calls = partition_tool_calls(pending)
    if not frontend_tool_calls:
        return {
            "internal_messages": state.internal_messages,
            "ui_messages": state.ui_messages,
        }

    internal_messages_to_add: list[ToolMessage] = []
    ui_messages_to_add: list[ToolMessage] = []

    for tool_call in frontend_tool_calls:
        name = tool_call_name(tool_call)
        tc_id = tool_call_id(tool_call)
        if not name or not tc_id:
            continue
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {}) or {}
        logger.info("Frontend tool pending (interrupt not wired yet): %s", name)
        raw = ToolMessage(
            content=_FRONTEND_NOT_WIRED_JSON,
            tool_call_id=tc_id,
            name=name,
        )
        llm_content = truncate_tool_result_for_llm(
            format_llm_tool_result(name, _FRONTEND_NOT_WIRED_JSON, tool_args=dict(args))
        )
        ui_content = format_ui_tool_result(name, _FRONTEND_NOT_WIRED_JSON, tool_args=dict(args))
        internal_messages_to_add.append(
            ToolMessage(content=llm_content, tool_call_id=tc_id, name=name)
        )
        ui_messages_to_add.append(ToolMessage(content=ui_content, tool_call_id=tc_id, name=name))

    return {
        "internal_messages": state.internal_messages + internal_messages_to_add,
        "ui_messages": state.ui_messages + ui_messages_to_add,
    }
