"""
Streamlit entry point for the EDS Pipeline Management UI.

Run with:
    streamlit run pipeline_app/main.py
"""

from pipeline_app.core.logging_service import LoggingService

LoggingService.setup()

import streamlit as st

from pipeline_app.ui.helpers import ensure_session_state, get_config
from pipeline_app.startup import get_scheduler, get_file_watcher

logger = LoggingService.get_logger(__name__)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pipeline Management",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

ensure_session_state()

st.session_state.scheduler = get_scheduler()
st.session_state.file_watcher = get_file_watcher()

# ---------------------------------------------------------------------------
# Sidebar (rendered on every page)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Pipeline Management")
    st.divider()

    config = get_config()
    st.markdown(f"**Project:** {config.project_name}")
    st.markdown(f"**Database:** {config.project_name.lower().strip()}")

    sched = st.session_state.get("scheduler")
    if sched is not None and sched.running:
        st.markdown("**Scheduler:** Running")
    else:
        st.markdown("**Scheduler:** Stopped")

    watcher = st.session_state.get("file_watcher")
    if watcher is not None and watcher.running:
        st.markdown("**File Watcher:** Running")
    else:
        st.markdown("**File Watcher:** Stopped")

    active = st.session_state.get("active_run")
    if active:
        st.markdown(f"**Active run:** {active}")

    st.divider()

# ---------------------------------------------------------------------------
# Landing content (shown when no page is selected)
# ---------------------------------------------------------------------------

st.header("Pipeline Management")
st.write(
    "Use the sidebar to navigate between pages: "
    "Overview, Run Flows, Schedules, Run History, and Settings."
)
