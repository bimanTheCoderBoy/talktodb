"""Run History page -- persistent audit trail from pipeline_metadata."""

import pandas as pd
import streamlit as st

from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import MetadataRepository
from pipeline_app.ui.helpers import ensure_session_state, get_config, run_async

ensure_session_state()

st.header("Run History")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

flow_options = ["All", "location", "mu", "cell", "audit"]

c1, c2 = st.columns(2)
with c1:
    entity_filter = st.selectbox("Flow", flow_options)
with c2:
    max_rows = st.number_input("Max rows", value=50, min_value=10, max_value=500, step=10)

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------


async def _fetch_history(table_filter: str | None) -> list[dict]:
    config = get_config()
    db = DatabaseManager.from_config(config)
    try:
        await db.provision(create_db=False, setup_rls=False, create_indexes=False)
        repo = MetadataRepository(db)
        return await repo.get_summary(
            config.project_name,
            table_name=table_filter,
        )
    finally:
        await db.dispose()


table_filter = entity_filter if entity_filter != "All" else None

try:
    rows = run_async(_fetch_history(table_filter))
except Exception as exc:
    st.error(f"Failed to fetch run history: {exc}")
    rows = []

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

if not rows:
    st.info("No run history found for the current project and filters.")
else:
    display_rows = rows[:max_rows]
    df = pd.DataFrame(display_rows)

    column_order = [
        "id",
        "entity_type",
        "run_type",
        "status",
        "total_records",
        "records_processed",
        "error_message",
        "started_at",
        "completed_at",
    ]
    available = [c for c in column_order if c in df.columns]
    df = df[available]

    rename_map = {
        "id": "ID",
        "entity_type": "Entity Type",
        "run_type": "Run Type",
        "status": "Status",
        "total_records": "Total Records",
        "records_processed": "Processed",
        "error_message": "Error",
        "started_at": "Started At",
        "completed_at": "Completed At",
    }
    df = df.rename(columns=rename_map)

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(display_rows)} of {len(rows)} rows")

    csv_data = df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name="run_history.csv",
        mime="text/csv",
    )
