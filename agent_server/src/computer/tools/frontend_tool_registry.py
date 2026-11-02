from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TypeVar



F = TypeVar("F", bound=Callable[..., object])
"""
For Learning:
'F' is a generic type created by the TypeVar class.
here bound tells the specific type of the function that is being passed to the decorator.
Callable[..., object] : ... means function can take any args and object means return type is object

Example:
TestT1=TypeVar("TestT1", bound=int) # single type

TestT2=TypeVar("TestT2", int, float, bool) # multiple types

"""

class FrontendToolRegistry:
    """Registry of tool names executed on the client (not via server ToolNode)."""

    _lock: Lock = Lock()
    _instance: FrontendToolRegistry | None = None
    _tool_names: set[str] = set()
    _handlers: dict[str, Callable[..., object]] = {}

    def __new__(cls) -> FrontendToolRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, tool_name: str, handler: Callable[..., object] | None = None) -> None:
        normalized = tool_name.strip()
        if not normalized:
            raise ValueError("tool_name is required")
        self._tool_names.add(normalized)
        if handler is not None:
            self._handlers[normalized] = handler

    def is_frontend_tool(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        return tool_name.strip() in self._tool_names

    def get_handler(self, tool_name: str) -> Callable[..., object] | None:
        return self._handlers.get(tool_name.strip())

    def tool_names(self) -> frozenset[str]:
        return frozenset(self._tool_names)


def register_frontend_tool(tool_name: str) -> None:
    FrontendToolRegistry().register(tool_name)


def frontend_tool(tool_name: str) -> Callable[[F], F]:
    """Mark a callable / LangChain tool name as frontend-executed (registration side effect)."""

    def decorator(func: F) -> F:
        FrontendToolRegistry().register(tool_name, func)
        return func

    return decorator
