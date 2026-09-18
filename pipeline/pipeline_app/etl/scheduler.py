"""
Pipeline scheduler — cron-based scheduling via APScheduler.

Wraps APScheduler's BackgroundScheduler with a SQLAlchemyJobStore backed by
the existing PostgreSQL database.  APScheduler owns all persistence, cron
parsing, and missed-fire recovery; this module exposes a thin API for
Streamlit UI integration.

Usage::

    config = PipelineConfig.from_env()
    scheduler = PipelineScheduler(config)
    scheduler.start()

    scheduler.add_schedule("Nightly sync", hour=2, minute=0,
                           flow_names=["location", "mu", "cell", "audit"])
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline_app.core.config import PipelineConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.etl.orchestrator import PipelineOrchestrator
from pipeline_app.etl.registry import FLOW_REGISTRY

logger = LoggingService.get_logger(__name__)


def _build_sync_url(config: PipelineConfig) -> str:
    """Build a sync psycopg2 DB URL for the scheduler job store.

    Uses a fixed database (``SCHEDULER_DB`` env var, default ``pipeline_db``)
    so the scheduler is independent of the per-project databases.
    """
    import os
    db = config.db
    db_name = os.getenv("SCHEDULER_DB", "pipeline_db")
    return f"postgresql+psycopg2://{db.user}:{db.password}@{db.host}:{db.port}/{db_name}"


def _run_scheduled(
    flow_names: list[str],
    project_name: str,
    fail_fast: bool = True,
) -> None:
    """Sync job function invoked by BackgroundScheduler.

    Bridges into async via ``asyncio.run``.  Module-level functions serialise
    cleanly via pickle; instance methods and lambdas do not.

    *project_name* is persisted in the APScheduler job store so that the
    schedule always runs against the project that was active when the
    schedule was created — independent of the current env or UI config.
    """
    asyncio.run(_run_scheduled_async(flow_names, project_name, fail_fast))


async def _run_scheduled_async(
    flow_names: list[str],
    project_name: str,
    fail_fast: bool = True,
) -> None:
    """Async implementation — creates a fresh orchestrator per run."""
    valid_names = [f for f in flow_names if f in FLOW_REGISTRY]
    removed = set(flow_names) - set(valid_names)
    if removed:
        logger.warning(
            "Scheduled job references unknown flows (removed): %s — skipping them.",
            sorted(removed),
        )
    if not valid_names:
        logger.warning("Scheduled job has no valid flows after filtering — skipping run.")
        return

    fh = LoggingService.begin_run_log(f"scheduled_{'_'.join(valid_names)}")
    try:
        config = PipelineConfig.from_env()
        config.overwrite_project_name(project_name)
        async with PipelineOrchestrator(config, fail_fast=fail_fast) as orch:
            result = await orch.run_flows(valid_names)
        logger.info(
            "Scheduled run complete: project=%s, success=%s, inserted=%d\n%s",
            project_name,
            result.success,
            result.total_inserted,
            result.summary(),
        )
    finally:
        LoggingService.end_run_log(fh)


_JOB_DEFAULTS: Dict[str, Any] = {
    "max_instances": 1,
    "coalesce": True,
    "misfire_grace_time": 3600,
}


class PipelineScheduler:
    """Cron-based pipeline scheduler backed by PostgreSQL.

    Parameters
    ----------
    config:
        Pipeline configuration — used to derive the sync DB URL for
        APScheduler's ``SQLAlchemyJobStore``.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._scheduler: BackgroundScheduler | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect to PostgreSQL, load persisted jobs, and start the tick loop."""
        url = _build_sync_url(self._config)
        jobstore = SQLAlchemyJobStore(url=url)
        self._scheduler = BackgroundScheduler(
            jobstores={"default": jobstore},
            job_defaults=_JOB_DEFAULTS,
        )
        self._scheduler.start()
        logger.info("PipelineScheduler started (db=%s)", url.split("@")[-1])

    def shutdown(self, wait: bool = True) -> None:
        """Stop the scheduler.  *wait=True* lets a running pipeline finish."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=wait)
            logger.info("PipelineScheduler shut down (wait=%s)", wait)

    @property
    def running(self) -> bool:
        """Whether the scheduler tick loop is active."""
        return self._scheduler is not None and self._scheduler.running

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    def add_schedule(
        self,
        name: str,
        hour: int,
        minute: int,
        flow_names: list[str],
        project_name: str,
        *,
        fail_fast: bool = True,
    ) -> str:
        """Create (or overwrite) a cron schedule.

        *project_name* is captured at creation time and persisted in the
        APScheduler job store.  When the job fires it uses this stored
        value — not the env var or current UI config.

        Returns the generated job ID.
        """
        if self._scheduler is None:
            raise RuntimeError("Scheduler is not started — call start() first.")

        unknown = set(flow_names) - FLOW_REGISTRY.keys()
        if unknown:
            raise ValueError(
                f"Unknown flows: {unknown}. Valid: {sorted(FLOW_REGISTRY)}"
            )

        job_id = f"schedule_{name.lower().replace(' ', '_')}"
        self._scheduler.add_job(
            _run_scheduled,
            CronTrigger(hour=hour, minute=minute),
            id=job_id,
            name=name,
            kwargs={
                "flow_names": flow_names,
                "fail_fast": fail_fast,
                "project_name": project_name,
            },
            replace_existing=True,
        )
        logger.info(
            "Schedule added: %s (id=%s, %02d:%02d, project=%s)",
            name, job_id, hour, minute, project_name,
        )
        return job_id

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Return a list of schedule dicts for the UI."""
        if self._scheduler is None:
            return []
        schedules: List[Dict[str, Any]] = []
        for job in self._scheduler.get_jobs():
            kwargs = job.kwargs or {}
            schedules.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time,
                    "flow_names": kwargs.get("flow_names", []),
                    "project_name": kwargs.get("project_name"),
                    "trigger": str(job.trigger),
                    "paused": job.next_run_time is None,
                }
            )
        return schedules

    def remove_schedule(self, schedule_id: str) -> None:
        """Delete a schedule by ID."""
        self._scheduler.remove_job(schedule_id)
        logger.info("Schedule removed: %s", schedule_id)

    def pause_schedule(self, schedule_id: str) -> None:
        """Pause a schedule — it won't fire until resumed."""
        self._scheduler.pause_job(schedule_id)
        logger.info("Schedule paused: %s", schedule_id)

    def resume_schedule(self, schedule_id: str) -> None:
        """Resume a previously paused schedule."""
        self._scheduler.resume_job(schedule_id)
        logger.info("Schedule resumed: %s", schedule_id)

    def reschedule(self, schedule_id: str, hour: int, minute: int) -> None:
        """Change the time of an existing schedule."""
        self._scheduler.reschedule_job(
            schedule_id,
            trigger=CronTrigger(hour=hour, minute=minute),
        )
        logger.info("Schedule rescheduled: %s -> %02d:%02d", schedule_id, hour, minute)
