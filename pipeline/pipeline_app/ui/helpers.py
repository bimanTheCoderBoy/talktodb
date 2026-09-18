"""Shared helpers for the Streamlit UI layer."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, List

import streamlit as st

from pipeline_app.core.config import PipelineConfig
from pipeline_app.etl.result import PipelineResult

# ---------------------------------------------------------------------------
# Windows asyncio policy — must run before any event loop is created
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Status helpers (no emojis)
# ---------------------------------------------------------------------------

STATUS_ICON = {
    "success": "[OK]",
    "failed": "[FAIL]",
    "skipped": "[SKIP]",
}


def format_outcome_line(outcome) -> str:
    """One-line summary for a FlowOutcome."""
    icon = STATUS_ICON.get(outcome.status, "[?]")
    parts = [f"{icon} {outcome.name} -- {outcome.elapsed_seconds:.1f}s"]
    if outcome.status == "success":
        parts.append(f"fetched={outcome.total_fetched}, inserted={outcome.total_inserted}")
    elif outcome.status == "failed" and outcome.errors:
        parts.append(f"error: {outcome.errors[0][:80]}")
    elif outcome.status == "skipped":
        parts.append("dependency failed")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Async bridge
# ---------------------------------------------------------------------------

def run_async(coro) -> Any:
    """Execute an async coroutine from synchronous Streamlit code."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "pipeline_config": None,
    "run_history": [],
    "scheduler": None,
    "active_run": None,
}


def ensure_session_state() -> None:
    """Populate missing session-state keys with defaults."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            if isinstance(default, list):
                st.session_state[key] = list(default)
            else:
                st.session_state[key] = default


def get_config() -> PipelineConfig:
    """Return the cached PipelineConfig, creating it from env if absent."""
    if st.session_state.get("pipeline_config") is None:
        st.session_state.pipeline_config = PipelineConfig.from_env()
    return st.session_state.pipeline_config


def get_run_history() -> List[PipelineResult]:
    """Return the in-memory run history list."""
    return st.session_state.get("run_history", [])
