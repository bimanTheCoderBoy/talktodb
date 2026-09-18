import logging
import sys
import threading

class CustomLogger:
    _instance = None
    _lock = threading.Lock()

    def __init__(self ):
        if CustomLogger._instance is not None:
            raise RuntimeError("Use CustomLogger.get_instance() instead.")
        

    @classmethod
    def initialize(cls, name: str="app_logger"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger = logging.getLogger(name)
                    if not logger.handlers:
                        logger.setLevel(logging.INFO)
                        log_format = logging.Formatter( "[%(asctime)s] %(levelname)s in %(filename)s (Line %(lineno)d, Func: %(funcName)s): %(message)s")
                        console_handler = logging.StreamHandler(sys.stdout)
                        console_handler.setFormatter(log_format)
                        logger.addHandler(console_handler)
                    cls._instance.logger = logger

                    logger.info(f"Logger {name} initialized successfully with singleton object")
    @classmethod
    def get_instance(cls) -> logging.Logger:
        if cls._instance is None:
            raise RuntimeError("Logger not initialized Call initialize() at startup.")
        return cls._instance.logger