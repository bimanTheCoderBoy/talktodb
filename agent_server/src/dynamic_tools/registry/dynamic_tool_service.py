from .dynamic_tool_registry import DynamicToolRegistry
from typing import Dict, List, Any
import inspect
import logging
from .model import DynamicTool
from .schema import DynamicToolDefinitionResult, DynamicToolDefinition, DynamicToolCallResult

logger = logging.getLogger(__name__)

class DynamicToolService:

    def __init__(self) -> None:
        self._registry: DynamicToolRegistry | None = None

    async def _get_registry(self) -> DynamicToolRegistry:
        if self._registry is None:
            self._registry = await DynamicToolRegistry.get_instance()
        return self._registry

    async def callDynamicTool(self, name: str, args: Dict[str, Any]) -> DynamicToolCallResult:
        """call the dynamic tool with the given name and args"""
        registry = await self._get_registry()
        try:
            tool = registry.get(name) # raise ValueError if not found

            validated_args = tool.input_schema.model_validate(args) # raise ValidationError if invalid

            result = tool.callable(**dict(validated_args))
            if inspect.isawaitable(result):
                # check if result is awaitable
                result = await result

            return DynamicToolCallResult(
                success=True,
                error=None,
                result=result,
            )

        except Exception as e:
            logger.exception("[DYNAMIC_TOOLS] callDynamicTool failed for %r", name)
            return DynamicToolCallResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                result=None,
            )

    async def getDynamicTool(self, tool_name_or_pattern: str) -> DynamicToolDefinitionResult:
        """get the dynamic tool if exact match, otherwise return the best matches with name & description"""
        registry = await self._get_registry()
        try:
            tools: List[DynamicTool] = []
            try:
                tools.append(registry.get(tool_name_or_pattern)) # raise ValueError if not found

            except ValueError:
                tools.extend(registry.list(tool_name_or_pattern))

            return DynamicToolDefinitionResult(
                success=True,
                tools=[_to_definition(tool) for tool in tools],
            )

        except Exception as e:
            logger.exception("[DYNAMIC_TOOLS] getDynamicTool failed for %r", tool_name_or_pattern)
            return DynamicToolDefinitionResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                tools=None,
            )


def _to_definition(tool: DynamicTool) -> DynamicToolDefinition:
    return DynamicToolDefinition(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema.model_json_schema(),
    )
