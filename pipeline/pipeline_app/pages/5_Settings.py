"""Settings page -- runtime project configuration."""

import json
import os

import streamlit as st

from pipeline_app.ui.helpers import ensure_session_state, get_config

ensure_session_state()

st.header("Settings")

# ---------------------------------------------------------------------------
# Project name editor
# ---------------------------------------------------------------------------

st.subheader("Project Configuration")

config = get_config()

new_name = st.text_input("Project Name", value=config.project_name)

if st.button("Save"):
    stripped = new_name.strip()
    if not stripped:
        st.error("Project name cannot be empty.")
    elif stripped == config.project_name:
        st.info("No change detected.")
    else:
        try:
            config.overwrite_project_name(stripped)
            os.environ["PROJECT_NAME"] = stripped
            os.environ["EDS_QUERY_FILTER"] = config.api.query_filter
            st.success(f"Project name updated to: {stripped}")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to update project name: {exc}")

# ---------------------------------------------------------------------------
# Current configuration (read-only)
# ---------------------------------------------------------------------------

st.subheader("Runtime Configuration")

runtime_info = {
    "project_name": config.project_name,
    "database": config.project_name.lower().strip(),
    "db_host": config.db.host,
    "db_port": config.db.port,
    "api_base_url": config.api.base_url,
    "query_filter": config.api.query_filter,
    "max_concurrent": config.api.max_concurrent,
}

st.json(json.dumps(runtime_info, indent=2, default=str))
