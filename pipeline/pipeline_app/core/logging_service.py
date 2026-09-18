"""
Centralized logging service for the pipeline.

Usage in any module:
    from pipeline_app.core.logging_service import LoggingService
    logger = LoggingService.get_logger(__name__)

Initialization (call ONCE at process start):
    from pipeline_app.core.logging_service import LoggingService
    LoggingService.setup()
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class LoggingService:
    """
    Singleton logging service that configures and manages the pipeline's
    logging infrastructure.

    All methods are classmethods — modules interact exclusively through
    this class and never touch stdlib logging configuration directly.
    """

    _DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    _NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "asyncio", "apscheduler")

    _initialized: bool = False
    _root: Optional[logging.Logger] = None
    _level: str = "INFO"
    _formatter: Optional[logging.Formatter] = None
    _log_file: Optional[Path] = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @classmethod
    def setup(
        cls,
        level: Optional[str] = None,
    ) -> None:
        """
        Configure the root logger (console only). Idempotent.

        File logging is handled per-execution via begin_run_log/end_run_log.

        Env variables (used when args are None):
            LOG_LEVEL — DEBUG | INFO | WARNING | ERROR  (default: INFO)
        """
        if cls._initialized:
            return
        cls._initialized = True

        cls._level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
        cls._formatter = logging.Formatter(cls._DEFAULT_FORMAT, datefmt=cls._DATE_FORMAT)

        cls._root = logging.getLogger()
        cls._root.setLevel(cls._level)
        cls._root.handlers.clear()

        # Console handler (stdout)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(cls._level)
        console.setFormatter(cls._formatter)
        cls._root.addHandler(console)

        # Silence noisy third-party loggers
        for name in cls._NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Per-execution file logging
    # ------------------------------------------------------------------

    @classmethod
    def begin_run_log(cls, flow_label: str) -> Optional[logging.FileHandler]:
        """
        Create and attach a per-run file handler named after the flow(s).

        Returns the handler so the caller can pass it to end_run_log().
        Returns None if LOG_FILE_ENABLED is false.

        File: {LOG_DIR}/{sanitized_label}_{YYYYMMDD}_{HHMMSS}.log
        """
        file_enabled = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"
        if not file_enabled:
            return None

        log_dir = Path(os.getenv("LOG_DIR", "./teoco_data_store/logs/streamlit_logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        safe_name = flow_label.replace(",", "").replace(" ", "_").lower().strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls._log_file = log_dir / f"{safe_name}_{timestamp}.log"

        fh = logging.FileHandler(cls._log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            cls._formatter or logging.Formatter(cls._DEFAULT_FORMAT, datefmt=cls._DATE_FORMAT)
        )
        logging.getLogger().addHandler(fh)
        return fh

    @classmethod
    def end_run_log(cls, handler: Optional[logging.FileHandler]) -> None:
        """Detach and close the per-run file handler."""
        if handler is None:
            return
        logging.getLogger().removeHandler(handler)
        handler.close()
        cls._log_file = None

    # ------------------------------------------------------------------
    # Logger factory
    # ------------------------------------------------------------------

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Return a named logger. Modules should call with __name__.

        Works even before setup() — messages buffer until the root
        logger receives handlers.
        """
        return logging.getLogger(name)

    # ------------------------------------------------------------------
    # Runtime handler management
    # ------------------------------------------------------------------

    @classmethod
    def add_handler(cls, handler: logging.Handler, level: Optional[str] = None) -> None:
        """Attach an extra handler to the root logger at runtime."""
        if level:
            handler.setLevel(getattr(logging, level.upper(), logging.DEBUG))
        if not handler.formatter:
            handler.setFormatter(
                cls._formatter or logging.Formatter(cls._DEFAULT_FORMAT, datefmt=cls._DATE_FORMAT)
            )
        logging.getLogger().addHandler(handler)

    @classmethod
    def remove_handler(cls, handler: logging.Handler) -> None:
        """Detach a previously-attached handler from the root logger."""
        logging.getLogger().removeHandler(handler)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @classmethod
    def get_log_file(cls) -> Optional[Path]:
        """Return the current run's log file path, or None if file logging is disabled."""
        return cls._log_file

    @classmethod
    def is_initialized(cls) -> bool:
        """Return whether setup() has been called."""
        return cls._initialized

    @classmethod
    def current_level(cls) -> str:
        """Return the configured log level string."""
        return cls._level
