from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis import Redis
from asp_app.db.redis import get_redis_client
from asp_app.services.redis_service import RedisService


router = APIRouter(
    prefix="/redis",
    tags=["Redis"]
)

@router.get("/logs/{acss_session_id}", response_class=StreamingResponse)
async def stream_logs(acss_session_id: str, redis_client: Redis = Depends(get_redis_client)):
    """SSE endpoint for streaming log messages."""
    return StreamingResponse(
        RedisService.stream_logs(redis_client, acss_session_id),
        media_type="text/event-stream"
    )

@router.get("/execution/{job_id}", response_class=StreamingResponse)
async def stream_execution_state(job_id: str, redis_client: Redis = Depends(get_redis_client)):
    """SSE endpoint for streaming execution state updates."""
    return StreamingResponse(
        RedisService.stream_execution_state(redis_client, job_id),
        media_type="text/event-stream"
    )
