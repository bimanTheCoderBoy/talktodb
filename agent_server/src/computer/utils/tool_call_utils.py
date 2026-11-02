from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from computer.state import AgentState
from computer.tools.frontend_tool_registry import FrontendToolRegistry


def tool_call_name(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        name = tool_call.get("name")
    else:
        name = getattr(tool_call, "name", None)
    return str(name) if name else None


def tool_call_id(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        tc_id = tool_call.get("id")
    else:
        tc_id = getattr(tool_call, "id", None)
    return str(tc_id) if tc_id else None


def get_last_ai_message_with_tool_calls(state: AgentState) -> AIMessage | None:
    for message in reversed(state.internal_messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            return message
    return None


def answered_tool_call_ids(state: AgentState, after_index: int) -> set[str]:
    answered: set[str] = set()
    for message in state.internal_messages[after_index + 1 :]:
        if isinstance(message, ToolMessage) and message.tool_call_id:
            answered.add(str(message.tool_call_id))
    return answered


def pending_tool_calls(state: AgentState) -> list[Any]:
    """Tool calls from the latest AI message that do not yet have a ToolMessage."""
    ai_message = get_last_ai_message_with_tool_calls(state)
    if not ai_message:
        return []

    ai_index = state.internal_messages.index(ai_message)
    answered = answered_tool_call_ids(state, ai_index)
    pending: list[Any] = []
    for tc in ai_message.tool_calls:
        tc_id = tool_call_id(tc)
        if tc_id and tc_id not in answered:
            pending.append(tc)
    return pending


def partition_tool_calls(
    tool_calls: list[Any],
) -> tuple[list[Any], list[Any]]:
    registry = FrontendToolRegistry()
    server_calls: list[Any] = []
    frontend_calls: list[Any] = []
    for tc in tool_calls:
        name = tool_call_name(tc)
        if name and registry.is_frontend_tool(name):
            frontend_calls.append(tc)
        else:
            server_calls.append(tc)
    return server_calls, frontend_calls


def has_pending_server_tool_calls(state: AgentState) -> bool:
    server, _ = partition_tool_calls(pending_tool_calls(state))
    return len(server) > 0


def has_pending_frontend_tool_calls(state: AgentState) -> bool:
    _, frontend = partition_tool_calls(pending_tool_calls(state))
    return len(frontend) > 0
