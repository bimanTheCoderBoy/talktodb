"""Schedules page -- CRUD for APScheduler cron jobs."""

from datetime import date, datetime, time as dt_time

import pytz
import streamlit as st

from pipeline_app.etl.registry import FLOW_REGISTRY
from pipeline_app.ui.helpers import ensure_session_state, get_config

ensure_session_state()

st.header("Schedules")

scheduler = st.session_state.get("scheduler")

if scheduler is None:
    st.error("Scheduler is not running. Check app startup logs.")
    st.stop()

# ---------------------------------------------------------------------------
# Scheduler status
# ---------------------------------------------------------------------------

st.markdown(f"**Scheduler status:** {'Running' if scheduler.running else 'Stopped'}")

# ---------------------------------------------------------------------------
# Active schedules list
# ---------------------------------------------------------------------------

st.subheader("Active Schedules")

schedules = scheduler.get_schedules()

if not schedules:
    st.info("No schedules configured. Create one below.")
else:
    for sched in schedules:
        cols = st.columns([3, 2, 2, 2, 1, 1, 1])
        cols[0].write(f"**{sched['name']}**")
        cols[1].write(sched.get("project_name") or "—")
        cols[2].write(", ".join(sched["flow_names"]))

        next_run = sched["next_run"]
        if next_run is not None:
            cols[3].write(next_run.strftime("%Y-%m-%d %H:%M"))
        else:
            cols[3].write("--")

        cols[4].write("Paused" if sched["paused"] else "Active")

        if sched["paused"]:
            if cols[5].button("Resume", key=f"resume_{sched['id']}"):
                scheduler.resume_schedule(sched["id"])
                st.rerun()
        else:
            if cols[5].button("Pause", key=f"pause_{sched['id']}"):
                scheduler.pause_schedule(sched["id"])
                st.rerun()

        if cols[6].button("Delete", key=f"del_{sched['id']}"):
            scheduler.remove_schedule(sched["id"])
            st.rerun()

    st.divider()

# ---------------------------------------------------------------------------
# Create schedule form
# ---------------------------------------------------------------------------

st.subheader("Create New Schedule")

config = get_config()

with st.form("create_schedule", clear_on_submit=True):
    name = st.text_input("Schedule name")
    schedule_project = st.text_input(
        "Project name (stored with schedule)",
        value=config.project_name,
    )
    run_at = st.time_input("Run at", value=dt_time(2, 0))
    flow_options = list(FLOW_REGISTRY.keys())
    flows = st.multiselect("Flows", options=flow_options, default=flow_options)
    fail_fast = st.checkbox("Fail fast", value=True)

    local_datetime = datetime.combine(date.today(), run_at)
    user_tz_name = st.context.timezone
    user_tz = pytz.timezone(user_tz_name)
    local_datetime = user_tz.localize(local_datetime)
    utc_zone = pytz.timezone('UTC')
    run_at_utc = local_datetime.astimezone(utc_zone)
    run_at_utc_time = run_at_utc.time()

    submitted = st.form_submit_button("Create Schedule")
    if submitted:
        if not name.strip():
            st.error("Schedule name cannot be empty.")
        elif not schedule_project.strip():
            st.error("Project name cannot be empty.")
        elif not flows:
            st.error("Select at least one flow.")
        else:
            try:
                job_id = scheduler.add_schedule(
                    name.strip(),
                    run_at_utc_time.hour,
                    run_at_utc_time.minute,
                    flows,
                    schedule_project.strip(),
                    fail_fast=fail_fast,
                )
                st.success(
                    f"Schedule created: {name.strip()} "
                    f"(project: {schedule_project.strip()}, id: {job_id})"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create schedule: {exc}")

# ---------------------------------------------------------------------------
# Reschedule existing
# ---------------------------------------------------------------------------

if schedules:
    with st.expander("Reschedule existing"):
        sched_options = {s["id"]: s["name"] for s in schedules}
        selected_id = st.selectbox(
            "Select schedule",
            options=list(sched_options.keys()),
            format_func=lambda x: sched_options[x],
        )
        new_time = st.time_input("New time", value=dt_time(2, 0), key="reschedule_time")

        if st.button("Update Time"):
            try:
                scheduler.reschedule(selected_id, new_time.hour, new_time.minute)
                st.success(
                    f"Rescheduled {sched_options[selected_id]} to "
                    f"{new_time.hour:02d}:{new_time.minute:02d}"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Reschedule failed: {exc}")
