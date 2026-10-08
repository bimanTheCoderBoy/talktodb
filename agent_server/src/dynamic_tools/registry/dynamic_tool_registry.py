import inspect
import threading
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List

from pydantic import BaseModel
from sqlalchemy.sql.functions import func

from .model import DynamicTool

DESCRIPTION_CLIP_LENGTH = 200
MIN_MATCH_SCORE = 50

class DynamicToolRegistry:
    _instance: 'DynamicToolRegistry | None' = None
    _lock: threading.Lock = threading.Lock()
    
    def __init__(self) -> None:
        if DynamicToolRegistry._instance is not None:
            raise ValueError("DynamicToolRegistry already initialized")
        self._tools: Dict[str, DynamicTool] = {}
        DynamicToolRegistry._instance = self


    @classmethod
    def get_instance_sync(cls) -> 'DynamicToolRegistry':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DynamicToolRegistry()
        return cls._instance

    @classmethod
    async def get_instance(cls) -> 'DynamicToolRegistry':
        return cls.get_instance_sync()

    def register(self, tool: DynamicTool) -> DynamicTool:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self._tools[tool.name] = tool
        return tool

    def unregister(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]
        else:
            raise ValueError(f"Tool {name} not found")


    def get(self, name: str) -> DynamicTool:
        if name in self._tools:
            return self._tools[name]
        else:
            raise ValueError(f"Tool {name} not found")

    def list(self, query: str | None = None) -> List[DynamicTool]:
        tools = list(self._tools.values())

        if not query or not query.strip():
            return [_summarize(tool) for tool in tools]

        query = query.strip().lower()
        scored: List[tuple[float, DynamicTool]] = []

        for tool in tools:
            name = tool.name.lower()
            description = tool.description.lower()

            if name == query:
                score = 100.0
            elif name.startswith(query):
                score = 90.0
            elif query in name:
                score = 80.0
            elif query in description:
                score = 60.0
            else:
                score = max(
                    _similarity_ratio(query, name),
                    _similarity_ratio(query, description),
                )

            if score >= MIN_MATCH_SCORE:
                scored.append((score, tool))

        scored.sort(key=lambda scored_tool: scored_tool[0], reverse=True)
        return [_summarize(tool) for _, tool in scored]


def _summarize(tool: DynamicTool) -> DynamicTool:
    description = tool.description
    if len(description) > DESCRIPTION_CLIP_LENGTH:
        description = description[:DESCRIPTION_CLIP_LENGTH].rstrip() + "... [truncated]"
    # copy so the clipped description never replaces the registered one
    return tool.model_copy(update={"description": description})


def _similarity_ratio(query: str, text: str) -> float:
    ratio = SequenceMatcher(None, query, text).ratio()
    return ratio * 100

def _check_signature(name: str, func: Callable[..., Any], input_schema: type[BaseModel]) -> None:
    parameters = inspect.signature(func).parameters
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values()):
        return

    fields = input_schema.model_fields
    unaccepted = [field for field in fields if field not in parameters]
    if unaccepted:
        raise ValueError(f"Tool {name} does not accept input_schema fields: {unaccepted}")

    undeclared = [
        param_name
        for param_name, param in parameters.items()
        if param.default is inspect.Parameter.empty
        and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and param_name not in fields
    ]
    if undeclared:
        raise ValueError(f"Tool {name} requires parameters missing from input_schema: {undeclared}")

def dynamicTool(name: str, description: str, input_schema: type[BaseModel]) -> Callable[[Callable[..., Any]], DynamicTool]:


    def decorator(func: Callable[..., Any]) -> DynamicTool:

        _check_signature(name, func, input_schema) # checking all the  func parameters  and input_schema fields are compatible

        tool = DynamicTool(name=name, description=description, input_schema=input_schema, callable=func)
        DynamicToolRegistry.get_instance_sync().register(tool)
        return tool


    return decorator
