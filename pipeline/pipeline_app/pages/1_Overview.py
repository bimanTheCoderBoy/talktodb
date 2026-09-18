"""Overview page -- dashboard with metrics, flow catalog, and recent runs."""

import pandas as pd
import streamlit as st

from pipeline_app.etl.registry import FLOW_REGISTRY
from pipeline_app.ui.helpers import (
    ensure_session_state,
    get_run_history,
    format_outcome_line,
)

ensure_session_state()

# ---------------------------------------------------------------------------
# Title + metrics
# ---------------------------------------------------------------------------

st.header("Pipeline Overview")

history = get_run_history()
success_count = sum(1 for r in history if r.success)
failed_count = len(history) - success_count

sched = st.session_state.get("scheduler")
sched_count = 0
if sched is not None:
    try:
        sched_count = len(sched.get_schedules())
    except Exception:
        pass

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Runs", len(history))
c2.metric("Successful", success_count)
c3.metric("Failed", failed_count)
c4.metric("Scheduled Jobs", sched_count)

# ---------------------------------------------------------------------------
# Flow catalog
# ---------------------------------------------------------------------------

st.subheader("Registered Flows")

catalog_rows = []
for spec in FLOW_REGISTRY.values():
    catalog_rows.append(
        {
            "Name": spec.name,
            "Category": spec.category,
            "Run Type": spec.run_type,
            "Depends On": ", ".join(spec.depends_on) if spec.depends_on else "--",
        }
    )

st.dataframe(pd.DataFrame(catalog_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Recent manual runs
# ---------------------------------------------------------------------------

st.subheader("Recent Manual Runs")

if not history:
    st.info("No runs yet. Go to Run Flows to execute a pipeline.")
else:
    for result in reversed(history[-5:]):
        label = (
            f"{result.imported_at:%Y-%m-%d %H:%M:%S} -- "
            f"{'OK' if result.success else 'FAILED'} -- "
            f"{result.total_elapsed:.1f}s"
        )
        with st.expander(label):
            for outcome in result.outcomes:
                st.text(format_outcome_line(outcome))
            st.code(result.summary(), language="text")
