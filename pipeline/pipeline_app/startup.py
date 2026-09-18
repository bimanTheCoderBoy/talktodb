from __future__ import annotations

from pipeline_app.core.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

_scheduler = None
_file_watcher = None
_boot_errors: dict[str, str] = {}


def _boot_once() -> None:
    """Initialise scheduler and file watcher.

    Safe to call multiple times — already-running services are skipped,
    previously-failed ones are retried.
    """
    global _scheduler, _file_watcher

    from pipeline_app.core.config import PipelineConfig
    from pipeline_app.etl.scheduler import PipelineScheduler
    from pipeline_app.etl.file_watcher import FileWatcherService

    if _scheduler is None or not _scheduler.running:
        try:
            config = PipelineConfig.from_env()
            sched = PipelineScheduler(config)
            sched.start()
            _scheduler = sched
            _boot_errors.pop("scheduler", None)
            logger.info("PipelineScheduler started")
        except Exception as exc:
            _boot_errors["scheduler"] = str(exc)
            logger.warning("Scheduler failed to start: %s", exc)

    if _file_watcher is None or not _file_watcher.running:
        try:
            config = PipelineConfig.from_env()
            watcher = FileWatcherService(config)
            watcher.start()
            _file_watcher = watcher
            _boot_errors.pop("file_watcher", None)
            logger.info("FileWatcherService started")
        except Exception as exc:
            _boot_errors["file_watcher"] = str(exc)
            logger.warning("FileWatcher failed to start: %s", exc)


_boot_once()


def get_scheduler():
    return _scheduler


def get_file_watcher():
    return _file_watcher


def get_boot_errors() -> dict[str, str]:
    """Return a dict of service name → error message for any that failed."""
    return dict(_boot_errors)


def retry_boot() -> None:
    """Re-attempt starting any services that previously failed."""
    _boot_once()
