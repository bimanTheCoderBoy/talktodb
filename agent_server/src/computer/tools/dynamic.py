from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from computer.config.logger import get_computer_logger
from dynamic_tools.registry import (
    DynamicToolCallResult,
    DynamicToolDefinitionResult,
    DynamicToolService,
)

import dynamic_tools.tools # noqa: F401

logger = get_computer_logger(__name__)

_DYNAMIC_TOOL_SERVICE = DynamicToolService()


class GetDynamicToolInput(BaseModel):
    tool_name_or_pattern: str = Field(
        default="",
        description="Exact dynamic tool name, or a keyword to search names and descriptions. Empty lists every registered dynamic tool.",
    )


class CallDynamicToolInput(BaseModel):
    name: str = Field(description="Exact dynamic tool name, as returned by get_dynamic_tool.")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the tool, shaped to the input_schema that get_dynamic_tool returned for it.",
    )


@tool("get_dynamic_tool", args_schema=GetDynamicToolInput, parse_docstring=False)
async def get_dynamic_tool(tool_name_or_pattern: str = "") -> str:
    """
    Discover dynamic tools that are registered at runtime and not listed in this tool list.

    Call this before call_dynamic_tool to learn a tool's exact name and argument schema.
    An exact name returns that one tool with its full description and input_schema as JSON Schema.
    A keyword returns ranked matches on name first, then description, then fuzzy matches.
    An empty value returns every available tool. Descriptions of search matches are clipped to
    200 characters, so look up the exact name when you need the full text before calling it.
    """
    logger.info("[DYNAMIC_TOOLS] get_dynamic_tool query=%r", tool_name_or_pattern)
    try:
        result = await _DYNAMIC_TOOL_SERVICE.getDynamicTool(tool_name_or_pattern)
    except Exception as exc:
        logger.exception("[DYNAMIC_TOOLS] get_dynamic_tool unexpected error")
        result = DynamicToolDefinitionResult(
            success=False,
            error=f"Unexpected error during dynamic tool lookup: {exc}",
            tools=None,
        )
    return result.model_dump_json()


@tool("call_dynamic_tool", args_schema=CallDynamicToolInput, parse_docstring=False)
async def call_dynamic_tool(name: str, args: dict[str, Any] | None = None) -> str:
    """
    Run a dynamic tool that was discovered with get_dynamic_tool.

    Use the exact name from get_dynamic_tool and pass args matching that tool's input_schema.
    Arguments are validated against the schema before the tool runs. Returns success with the
    tool's result, or success=false with the reason when the name is unknown, the arguments do
    not satisfy the schema, or the tool itself failed. On a schema error, re-read the tool's
    input_schema with get_dynamic_tool rather than guessing argument names.
    """
    logger.info("[DYNAMIC_TOOLS] call_dynamic_tool name=%r", name)
    try:
        result = await _DYNAMIC_TOOL_SERVICE.callDynamicTool(name, args or {})
    except Exception as exc:
        logger.exception("[DYNAMIC_TOOLS] call_dynamic_tool unexpected error")
        result = DynamicToolCallResult(
            success=False,
            error=f"Unexpected error during dynamic tool call: {exc}",
            result=None,
        )
    # a dynamic tool can return anything, so stringify whatever JSON cannot represent
    return json.dumps(result.model_dump(), default=str)


DYNAMIC_TOOLS: list[BaseTool] = [
    get_dynamic_tool,
    call_dynamic_tool,
]
