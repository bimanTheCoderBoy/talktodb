"""Run Flows page -- manual execution of pipeline flows."""

import streamlit as st

from pipeline_app.core.logging_service import LoggingService
from pipeline_app.etl.orchestrator import PipelineOrchestrator
from pipeline_app.etl.registry import FLOW_REGISTRY
from pipeline_app.ui.helpers import (
    ensure_session_state,
    get_config,
    run_async,
    format_outcome_line,
    STATUS_ICON,
)

ensure_session_state()

st.header("Run Flows")

# ---------------------------------------------------------------------------
# Execution helper
# ---------------------------------------------------------------------------


def _execute_flows(flow_names: list[str], fail_fast: bool, label: str):
    """Run the given flows via the orchestrator and display results."""
    if st.session_state.active_run:
        st.warning(f"A run is already in progress: {st.session_state.active_run}")
        return

    st.session_state.active_run = label

    async def _run():
        config = get_config()
        async with PipelineOrchestrator(config, fail_fast=fail_fast) as orch:
            return await orch.run_flows(flow_names)

    fh = LoggingService.begin_run_log(label)
    try:
        with st.spinner(f"Running {label} ..."):
            result = run_async(_run())
    except Exception as exc:
        st.error(f"Pipeline execution failed: {exc}")
        st.session_state.active_run = None
        return
    finally:
        LoggingService.end_run_log(fh)

    st.session_state.active_run = None
    st.session_state.run_history.append(result)

    if result.success:
        st.success(
            f"Pipeline completed successfully -- "
            f"{result.total_inserted} rows inserted in {result.total_elapsed:.1f}s"
        )
    else:
        st.error(
            f"Pipeline finished with failures: {', '.join(result.failed_flows)} -- "
            f"{result.total_elapsed:.1f}s"
        )

    for outcome in result.outcomes:
        st.text(format_outcome_line(outcome))

    with st.expander("Full summary"):
        st.code(result.summary(), language="text")


# ---------------------------------------------------------------------------
# Quick actions
# ---------------------------------------------------------------------------

st.subheader("Quick Actions")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("Run All Flows", use_container_width=True):
        _execute_flows(
            ["location", "mu", "cell", "audit"],
            fail_fast=True,
            label="All Flows",
        )

with c2:
    if st.button("Run Entity Flows", use_container_width=True):
        _execute_flows(
            ["location", "mu", "cell"],
            fail_fast=True,
            label="Entity Flows",
        )

with c3:
    if st.button("Run Audit Flows", use_container_width=True):
        _execute_flows(
            ["audit"],
            fail_fast=True,
            label="Audit Flows",
        )

# ---------------------------------------------------------------------------
# Custom selection
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Custom Selection")

all_flows = list(FLOW_REGISTRY.keys())

selected = st.multiselect("Select flows", options=all_flows, default=all_flows)
fail_fast = st.checkbox("Fail fast (stop on first failure)", value=True)

run_disabled = not selected or st.session_state.active_run is not None

if st.button("Run Selected", disabled=run_disabled, use_container_width=True):
    _execute_flows(selected, fail_fast=fail_fast, label=", ".join(selected))
