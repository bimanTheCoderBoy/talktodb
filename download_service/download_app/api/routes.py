"""API routes for the download service (PDF / MD / CSV)."""
import json
from typing import Iterator, Literal
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import redis
from celery.result import AsyncResult

from download_app.config import REDIS_URL
from download_app.tasks.celery_tasks import convert_md_to_file_task, celery_app

router = APIRouter()

CHUNK_SIZE = 64 * 1024


class ConvertRequest(BaseModel):
    markdown: str
    filetype: Literal["pdf", "md", "csv"] = "pdf"


class ConvertResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    error: str | None = None


@router.post("/convert", response_model=ConvertResponse)
async def convert_markdown(request: ConvertRequest):
    """Submit a markdown conversion job."""
    task = convert_md_to_file_task.delay(request.markdown, request.filetype)
    return ConvertResponse(job_id=task.id)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def check_status(job_id: str):
    """Check the status of a conversion job."""
    task_result = AsyncResult(job_id, app=celery_app)
    status = task_result.state
    error = None

    if status == "FAILURE":
        error = str(task_result.info) if task_result.info else "Unknown error"

    return StatusResponse(job_id=job_id, status=status, error=error)


def _stream_bytes(data: bytes) -> Iterator[bytes]:
    offset = 0
    total = len(data)
    while offset < total:
        yield data[offset:offset + CHUNK_SIZE]
        offset += CHUNK_SIZE


_FALLBACK_META = {
    "media_type": "application/pdf",
    "extension": "pdf",
}


@router.get("/download/{job_id}")
async def download_file(job_id: str):
    """
    Download the converted file for a completed job.

    Streams the file from Redis in 64 KB chunks. The content-type and
    filename extension are determined by the metadata stored alongside
    the file bytes when the Celery task completed.
    """
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=False)

    try:
        file_key = f"file:{job_id}"
        meta_key = f"meta:{job_id}"

        file_bytes = redis_client.get(file_key)
        if file_bytes is None:
            raise HTTPException(
                status_code=404,
                detail=f"File not found for job_id: {job_id}. Check job status first.",
            )

        raw_meta = redis_client.get(meta_key)
        meta = json.loads(raw_meta) if raw_meta else _FALLBACK_META

        media_type = meta.get("media_type", _FALLBACK_META["media_type"])
        extension = meta.get("extension", _FALLBACK_META["extension"])
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        return StreamingResponse(
            _stream_bytes(file_bytes),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="Report_{timestamp}.{extension}"',
                "Content-Length": str(len(file_bytes)),
            },
        )
    finally:
        redis_client.close()
