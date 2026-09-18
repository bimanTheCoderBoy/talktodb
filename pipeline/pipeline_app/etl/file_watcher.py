"""
Filesystem watcher — auto-triggers audit flows when new CSVs arrive.

Monitors ``OSS_CSV_FOLDER`` for new ``.csv`` files inside project subfolders::

    oss-csv/
      ├── Nos_Portugal/       ← project name derived from folder
      │     ├── 4G_export.csv
      │     └── 5G_export.csv
      └── Jersey/
            └── 4G_export.csv

When files land in ``oss-csv/<project_name>/``, the watcher:
    1. Debounces events (2 s) so paired 4G + 5G drops are batched.
    2. Writes a ``pipeline_metadata`` row with ``status="pending"``.
    3. Runs the audit flow via ``PipelineOrchestrator``.
    4. Updates the metadata row to ``success`` or ``failed``.
    5. Deletes source CSVs on success when ``AUTOMATIC_AUDIT_FLOW=true``.

Boot alongside Streamlit via ``@st.cache_resource`` in ``app.py``.
"""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from pipeline_app.core.config import PipelineConfig
from pipeline_app.core.logging_service import LoggingService
from pipeline_app.db.engine import DatabaseManager
from pipeline_app.db.repository import MetadataRepository
from pipeline_app.etl.orchestrator import PipelineOrchestrator

logger = LoggingService.get_logger(__name__)

_DEBOUNCE_SECONDS = 2.0
_POLL_INTERVAL = 3  # seconds between polls when using PollingObserver


def _needs_polling(path: Path) -> bool:
    """Return True when *path* lives on a filesystem where inotify won't
    deliver events — e.g. Docker bind-mounts from Windows (9p / CIFS).

    Detection heuristics (any match → poll):
      1. ``/.dockerenv`` exists (we're inside a container).
      2. The mount backing *path* uses a non-native fs type (9p, cifs, etc.).
    """
    if not os.path.exists("/.dockerenv"):
        return False

    try:
        with open("/proc/mounts") as fh:
            resolved = str(path)
            for line in fh:
                parts = line.split()
                if len(parts) >= 3 and resolved.startswith(parts[1]):
                    fs_type = parts[2]
                    if fs_type in ("9p", "cifs", "fuse.grpcfuse", "fuse.sshfs", "nfs", "nfs4"):
                        logger.info(
                            "Mount for %s uses %s — falling back to PollingObserver",
                            path, fs_type,
                        )
                        return True
    except OSError:
        pass

    return False


def _create_observer(watch_path: Path):
    """Return the best available observer for *watch_path*."""
    if _needs_polling(watch_path):
        from watchdog.observers.polling import PollingObserver
        return PollingObserver(timeout=_POLL_INTERVAL)

    from watchdog.observers import Observer
    return Observer()


def _is_project_csv(event_path: Path, watch_root: Path) -> Optional[str]:
    """Return the project name if *event_path* is a CSV inside a project subfolder,
    or ``None`` if it should be ignored (root-level file, non-CSV, nested too deep)."""
    if event_path.suffix.lower() != ".csv":
        return None
    try:
        relative = event_path.relative_to(watch_root)
    except ValueError:
        return None
    # Expect exactly <project_name>/<file>.csv → 2 parts
    if len(relative.parts) != 2:
        return None
    return relative.parts[0]


class _AuditEventHandler(FileSystemEventHandler):
    """Watchdog handler that debounces per-project CSV arrivals."""

    def __init__(self, watch_root: Path, config: PipelineConfig) -> None:
        super().__init__()
        self._watch_root = watch_root
        self._config = config
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._running_projects: set[str] = set()

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        project = _is_project_csv(Path(event.src_path), self._watch_root)
        if project is None:
            return
        logger.info("File detected: %s (project=%s)", event.src_path, project)
        self._schedule(project)

    # ------------------------------------------------------------------

    def _schedule(self, project: str) -> None:
        with self._lock:
            existing = self._timers.pop(project, None)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(
                _DEBOUNCE_SECONDS,
                self._on_debounce_expired,
                args=(project,),
            )
            timer.daemon = True
            self._timers[project] = timer
            timer.start()

    def _on_debounce_expired(self, project: str) -> None:
        with self._lock:
            self._timers.pop(project, None)
            if project in self._running_projects:
                logger.warning(
                    "Audit already running for project '%s' — skipping.", project,
                )
                return
            self._running_projects.add(project)

        try:
            asyncio.run(self._run_audit(project))
        finally:
            with self._lock:
                self._running_projects.discard(project)

    # ------------------------------------------------------------------

    async def _run_audit(self, project: str) -> None:
        project_csv_dir = self._watch_root / project

        config = PipelineConfig.from_env()
        config.overwrite_project_name(project)

        fh = LoggingService.begin_run_log(f"auto_audit_{project}")
        meta_id: Optional[int] = None
        started_at = datetime.now()

        try:
            db = DatabaseManager.from_config(config)
            await db.provision(setup_rls=True)
            meta_repo = MetadataRepository(db)

            meta_id = await meta_repo.record_pending(
                project_name=project,
                entity_type="audit",
                run_type="auto_audit",
            )
            logger.info(
                "[auto_audit] project=%s  meta_id=%d — starting audit flow",
                project, meta_id,
            )

            async with PipelineOrchestrator(config, db=db) as orch:
                result = await orch.run_audit_flows()

            if result.success:
                await meta_repo.update_status(
                    meta_id,
                    status="success",
                    total_records=result.total_fetched,
                    records_processed=result.total_inserted,
                )
                logger.info(
                    "[auto_audit] project=%s — SUCCESS (fetched=%d, inserted=%d)",
                    project, result.total_fetched, result.total_inserted,
                )
                if self._config.auto_audit_enabled:
                    self._cleanup_csvs(project_csv_dir)
            else:
                error_msg = "; ".join(
                    e for o in result.outcomes for e in o.errors
                ) or "audit flow returned failure"
                await meta_repo.update_status(
                    meta_id,
                    status="failed",
                    total_records=result.total_fetched,
                    records_processed=result.total_inserted,
                    error_message=error_msg,
                )
                logger.error(
                    "[auto_audit] project=%s — FAILED: %s", project, error_msg,
                )

            await db.dispose()

        except Exception as exc:
            logger.error(
                "[auto_audit] project=%s — unhandled error: %s",
                project, exc, exc_info=True,
            )
            if meta_id is not None:
                try:
                    db_err = DatabaseManager.from_config(config)
                    await db_err.provision(setup_rls=False)
                    repo = MetadataRepository(db_err)
                    await repo.update_status(
                        meta_id,
                        status="failed",
                        error_message=str(exc),
                    )
                    await db_err.dispose()
                except Exception:
                    logger.warning(
                        "[auto_audit] could not update metadata for id=%d", meta_id,
                    )
        finally:
            LoggingService.end_run_log(fh)

    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_csvs(directory: Path) -> None:
        removed = 0
        for csv in directory.glob("*.csv"):
            try:
                csv.unlink()
                removed += 1
            except OSError as exc:
                logger.warning("Failed to delete %s: %s", csv, exc)
        if removed:
            logger.info("[auto_audit] Cleaned up %d CSV(s) from %s", removed, directory)


class FileWatcherService:
    """Process-level singleton that watches for new OSS CSVs.

    Parameters
    ----------
    config:
        Pipeline configuration — ``paths.oss_csv_folder`` determines the
        root directory to watch.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._watch_root = Path(config.paths.oss_csv_folder).resolve()
        self._observer = None

    def start(self) -> None:
        self._watch_root.mkdir(parents=True, exist_ok=True)

        handler = _AuditEventHandler(self._watch_root, self._config)
        self._observer = _create_observer(self._watch_root)
        self._observer.schedule(handler, str(self._watch_root), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        logger.info(
            "FileWatcherService started — watching %s (observer=%s)",
            self._watch_root,
            type(self._observer).__name__,
        )

    def shutdown(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("FileWatcherService shut down")

    @property
    def running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
