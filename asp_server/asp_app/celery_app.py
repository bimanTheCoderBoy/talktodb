# import os
# os.environ["PROJ_LIB"] = os.path.join(
#     os.path.dirname(os.path.dirname(os.__file__)),
#     "Lib", "site-packages", "rasterio", "proj_data",
# )

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

from asp_app.config.acss_config import get_redis_config

REDIS_URL = get_redis_config().redis_url

# Use different Redis databases for broker and backend (like PDF service)
# Broker = db 1, Backend = db 0
CELERY_BROKER_URL = f"{REDIS_URL}/1" if not REDIS_URL.endswith(("/0", "/1")) else REDIS_URL.rsplit("/", 1)[0] + "/1"
CELERY_BACKEND_URL = f"{REDIS_URL}/0" if not REDIS_URL.endswith(("/0", "/1")) else REDIS_URL.rsplit("/", 1)[0] + "/0"

celery_app = Celery(
    "acss_backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BACKEND_URL,
    include=["asp_app.tasks.execution_tasks"]
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_ignore_result=False,
    # Queue Routing (only ACSS tasks - download service has its own Celery app)
    task_default_queue='default',
    task_routes={
        "acss_service": {"queue": "acss_heavy"},
    }
)

if __name__ == "__main__":
    celery_app.start()
