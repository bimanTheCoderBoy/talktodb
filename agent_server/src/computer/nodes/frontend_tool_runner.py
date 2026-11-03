import json

from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from computer.state import AgentState, ctx_schema_State
from computer.tools.frontend_tool_registry import FrontendToolRegistry
from computer.utils.frontend_tool import build_interrupt_payload, frontend_tool_error_json, parse_interrupt_result
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





async def frontend_tool_runner(state: AgentState, runtime: Runtime[ctx_schema_State]):
    """Runner for frontend tools (interrupt/resume wiring added in a later step)."""

    pending = pending_tool_calls(state)
    _, frontend_tool_calls = partition_tool_calls(pending)
    if not frontend_tool_calls:
        return {
            "internal_messages": state.internal_messages,
            "ui_messages": state.ui_messages,
        }

    registry = FrontendToolRegistry()
    internal_messages_to_add: list[ToolMessage] = []
    ui_messages_to_add: list[ToolMessage] = []

    for tool_call in frontend_tool_calls:
        name = tool_call_name(tool_call)
        tc_id = tool_call_id(tool_call)
        if not name or not tc_id:
            continue
        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {}) or {}
        if not isinstance(args, dict):
            args = {}


        # Validate the arguments
        validated_args, args_error = registry.validate_request(name, args)
        if args_error:
            result_json = frontend_tool_error_json(args_error)
            tool_args_for_format = dict(args)
        else:
            assert validated_args is not None

            # Build the interrupt payload and send it to the frontend
            interrupt_payload = build_interrupt_payload(name, validated_args, tc_id)
            raw_result = interrupt(interrupt_payload)
            parsed, parse_error = parse_interrupt_result(raw_result)

            if parse_error:
                result_json = frontend_tool_error_json(parse_error)
                tool_args_for_format = validated_args
            else:
                assert parsed is not None
                validated_response, response_error = registry.validate_response(name, parsed)
                if response_error:
                    result_json = frontend_tool_error_json(response_error)
                else:
                    assert validated_response is not None
                    result_json = json.dumps(validated_response)
                tool_args_for_format = validated_args



                

        # Format the result for the LLM and UI
        llm_content = truncate_tool_result_for_llm(
            format_llm_tool_result(name, result_json, tool_args=tool_args_for_format)
        )
        ui_content = format_ui_tool_result(name, result_json, tool_args=tool_args_for_format)
        internal_messages_to_add.append(
            ToolMessage(content=llm_content, tool_call_id=tc_id, name=name)
        )
        ui_messages_to_add.append(ToolMessage(content=ui_content, tool_call_id=tc_id, name=name))

    return {
        "internal_messages": state.internal_messages + internal_messages_to_add,
        "ui_messages": state.ui_messages + ui_messages_to_add,
    }
