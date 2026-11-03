from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import Command

from computer.config.logger import get_computer_logger
from computer.state import AgentState, ctx_schema_State
from computer.tools import get_computer_tools_for_user
from computer.utils.tool_call_utils import partition_tool_calls, pending_tool_calls
from computer.utils.tool_result_format import (
    format_llm_tool_result,
    format_ui_tool_result,
    truncate_tool_result_for_llm,
)

logger = get_computer_logger(__name__)


def _tool_call_registry(tool_calls: list[Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    registry: dict[str, tuple[str, dict[str, Any]]] = {}
    for tc in tool_calls:
        if isinstance(tc, dict):
            tc_id = tc.get("id")
            name = tc.get("name")
            args = tc.get("args") or {}
        else:
            tc_id = getattr(tc, "id", None)
            name = getattr(tc, "name", None)
            args = getattr(tc, "args", None) or {}
        if tc_id and name:
            registry[str(tc_id)] = (str(name), dict(args))
    return registry


def _split_tool_message_for_channels(
    message: ToolMessage,
    registry: dict[str, tuple[str, dict[str, Any]]],
) -> tuple[ToolMessage, ToolMessage]:
    tc_id = message.tool_call_id
    tool_name, tool_args = registry.get(str(tc_id), (None, {}))
    if not tool_name:
        llm_message = message.model_copy(
            update={"content": truncate_tool_result_for_llm(message.content)}
        )
        return llm_message, message
    llm_content = truncate_tool_result_for_llm(
        format_llm_tool_result(tool_name, message.content, tool_args=tool_args)
    )
    ui_content = format_ui_tool_result(tool_name, message.content, tool_args=tool_args)
    return (
        ToolMessage(content=llm_content, tool_call_id=tc_id, name=tool_name),
        ToolMessage(content=ui_content, tool_call_id=tc_id, name=tool_name),
    )


async def tool_node_wrapper(state: AgentState, runtime: Runtime[ctx_schema_State]):
    user_email = getattr(runtime.context, "user_email", None) or getattr(state, "user_email", None)
    if not user_email:
        logger.error(
            "No user email found in runtime context or in the state. "
            "provide a user email in the runtime context or in the state."
        )
        raise ValueError(
            "No user email found in runtime context or in the state. "
            "provide a user email in the runtime context or in the state."
        )

    pending = pending_tool_calls(state)
    server_tool_calls, _ = partition_tool_calls(pending)
    if not server_tool_calls:
        return {"internal_messages": state.internal_messages}

    fs_tools = await get_computer_tools_for_user(user_email)
    tool_node = ToolNode(tools=fs_tools)

    tool_call_registry = _tool_call_registry(server_tool_calls)
    tool_outputs = await tool_node.ainvoke(server_tool_calls)
    if isinstance(tool_outputs, dict):
        tool_outputs = tool_outputs.get("messages", [])
    logger.info("Tool outputs: %s", tool_outputs)

    internal_messages_to_add = []
    ui_messages_to_add = []
    compiled_updates = {}
    compiled_goto = []
    is_a_command = False
    """Here We are mergeing if we get multiple Commands from parallel Tool Call"""


    for item in tool_outputs:
        if isinstance(item, Command):
            is_a_command = True
            # Track and merge dynamic routing destinations
            if item.goto:
                if isinstance(item.goto, list):
                    compiled_goto.extend(item.goto)
                else:
                    compiled_goto.append(item.goto)
            
            # Unpack and merge state dictionaries
            if item.update:
                for key, val in item.update.items():
                    if key == "internal_messages":
                        internal_messages_to_add.extend(val if isinstance(val, list) else [val])
                    elif key == "ui_messages":
                        ui_messages_to_add.extend(val if isinstance(val, list) else [val])
                    else:
                        # Non-reducer updates: later items overwrite earlier ones
                        compiled_updates[key] = val
        elif isinstance(item, ToolMessage):
            internal_msg, ui_msg = _split_tool_message_for_channels(item, tool_call_registry)
            internal_messages_to_add.append(internal_msg)
            ui_messages_to_add.append(ui_msg)
        else:
            internal_messages_to_add.append(item)
            ui_messages_to_add.append(item)

    compiled_updates["internal_messages"] = state.internal_messages + internal_messages_to_add
    compiled_updates["ui_messages"] = state.ui_messages + ui_messages_to_add

    if is_a_command:
        return Command(
            goto=compiled_goto,
            update=compiled_updates,
        )
    return compiled_updates
