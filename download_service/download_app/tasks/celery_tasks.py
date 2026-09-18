"""Celery tasks for the download service (PDF / MD / CSV)."""
import asyncio
import json
from celery import Celery
import redis

from download_app.config import CELERY_BROKER_URL, REDIS_URL
from download_app.services.md_to_pdf import md_to_pdf
from download_app.services.md_table_to_csv import extract_first_table_as_csv

celery_app = Celery(
    "download_service",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_ignore_result=False,
    task_default_queue="default",
    task_routes={
        "download_service": {"queue": "download_fast"},
    },
)

FILETYPE_CONFIG = {
    "pdf": {"media_type": "application/pdf", "extension": "pdf"},
    "md": {"media_type": "text/markdown; charset=utf-8", "extension": "md"},
    "csv": {"media_type": "text/csv; charset=utf-8", "extension": "csv"},
}

TTL_SECONDS = 3600


@celery_app.task(name="download_service", bind=True)
def convert_md_to_file_task(self, md_content: str, filetype: str = "pdf"):
    """
    Convert markdown to the requested file type and store result in Redis.

    Args:
        md_content: Markdown content to convert
        filetype: One of "pdf", "md", "csv"

    Returns:
        Success message with task_id and size
    """
    if filetype not in FILETYPE_CONFIG:
        raise ValueError(f"Unsupported filetype: {filetype}")

    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
    task_id = self.request.id
    file_key = f"file:{task_id}"
    meta_key = f"meta:{task_id}"

    try:
        cfg = FILETYPE_CONFIG[filetype]

        if filetype == "pdf":
            file_bytes = asyncio.run(md_to_pdf(md_content, return_bytes=True))
        elif filetype == "md":
            file_bytes = md_content.encode("utf-8")
        elif filetype == "csv":
            csv_text = extract_first_table_as_csv(md_content)
            if csv_text is None:
                raise ValueError("No markdown table found in the provided content")
            file_bytes = csv_text.encode("utf-8")

        meta = json.dumps({
            "filetype": filetype,
            "media_type": cfg["media_type"],
            "extension": cfg["extension"],
        })

        pipe = redis_client.pipeline()
        pipe.setex(file_key, TTL_SECONDS, file_bytes)
        pipe.setex(meta_key, TTL_SECONDS, meta.encode("utf-8"))
        pipe.execute()

        return {"status": "success", "task_id": task_id, "size": len(file_bytes)}

    except Exception:
        raise
    finally:
        redis_client.close()
