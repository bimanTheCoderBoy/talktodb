import subprocess
import sys
import signal

from pipeline_app.core.logging_service import LoggingService

LoggingService.setup()

logger = LoggingService.get_logger(__name__)


def main():
    from pipeline_app.startup import get_scheduler, get_file_watcher

    sched = get_scheduler()
    watcher = get_file_watcher()

    logger.info(
        "Background services ready  scheduler=%s  file_watcher=%s",
        "running" if sched and sched.running else "off",
        "running" if watcher and watcher.running else "off",
    )

    import pipeline_app.main as _main_mod
    _main_path = _main_mod.__file__

    cmd = [
        sys.executable, "-m", "streamlit", "run", _main_path,
        "--server.port=8501", "--server.address=0.0.0.0",
        "--browser.gatherUsageStats=false",
    ]

    proc = subprocess.Popen(cmd)

    def _shutdown(sig, frame):
        proc.terminate()
        if watcher:
            watcher.shutdown()
        if sched:
            sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
