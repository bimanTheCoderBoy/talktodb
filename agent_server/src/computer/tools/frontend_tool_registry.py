from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

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


@dataclass(frozen=True)
class FrontendToolEntry:
    tool_name: str
    handler: Callable[..., object] | None = None
    request_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None


class FrontendToolRegistry:
    """Registry of tool names executed on the client (not via server ToolNode)."""

    _lock: Lock = Lock()
    _instance: FrontendToolRegistry | None = None
    _entries: dict[str, FrontendToolEntry] = {}

    def __new__(cls) -> FrontendToolRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self,
        tool_name: str,
        handler: Callable[..., object] | None = None,
        *,
        request_model: type[BaseModel] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> None:
        normalized = tool_name.strip()
        if not normalized:
            raise ValueError("tool_name is required")

        existing = self._entries.get(normalized)
        if existing is not None and handler is None:
            self._entries[normalized] = FrontendToolEntry(
                tool_name=normalized,
                handler=existing.handler,
                request_model=request_model or existing.request_model,
                response_model=response_model or existing.response_model,
            )
            return

        self._entries[normalized] = FrontendToolEntry(
            tool_name=normalized,
            handler=handler if handler is not None else (existing.handler if existing else None),
            request_model=request_model
            if request_model is not None
            else (existing.request_model if existing else None),
            response_model=response_model
            if response_model is not None
            else (existing.response_model if existing else None),
        )

    def get_entry(self, tool_name: str) -> FrontendToolEntry | None:
        return self._entries.get(tool_name.strip())

    def is_frontend_tool(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        return tool_name.strip() in self._entries

    def get_handler(self, tool_name: str) -> Callable[..., object] | None:
        entry = self.get_entry(tool_name)
        return entry.handler if entry else None

    def tool_names(self) -> frozenset[str]:
        return frozenset(self._entries)

    def validate_request(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        entry = self.get_entry(tool_name)
        if entry is None or entry.request_model is None:
            return dict(args), None
        try:
            validated = entry.request_model.model_validate(args)
        except ValidationError as exc:
            return None, f"Invalid tool arguments: {exc}"
        return validated.model_dump(mode="json"), None

    def validate_response(
        self,
        tool_name: str,
        data: Any,
    ) -> tuple[dict[str, Any] | None, str | None]:
        entry = self.get_entry(tool_name)
        if not isinstance(data, dict):
            return None, "Tool response must be a JSON object."
        if entry is None or entry.response_model is None:
            return data, None
        try:
            validated = entry.response_model.model_validate(data)
        except ValidationError as exc:
            return None, f"Invalid tool response: {exc}"
        return validated.model_dump(mode="json"), None


def register_frontend_tool(tool_name: str) -> None:
    FrontendToolRegistry().register(tool_name)


def frontend_tool(
    tool_name: str,
    *,
    request_model: type[BaseModel] | None = None,
    response_model: type[BaseModel] | None = None,
) -> Callable[[F], F]:
    """Mark a callable / LangChain tool name as frontend-executed (registration side effect)."""

    def decorator(func: F) -> F:
        FrontendToolRegistry().register(
            tool_name,
            func,
            request_model=request_model,
            response_model=response_model,
        )
        return func

    return decorator
