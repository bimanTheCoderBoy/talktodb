"""FastAPI application entry point for the download service."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis

from download_app.config import REDIS_URL, API_TITLE, API_VERSION, API_DESCRIPTION
from download_app.api import routes

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=False)


def get_redis_client():
    """Get Redis client from pool."""
    return redis.Redis(connection_pool=redis_pool)


app.include_router(routes.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "redis": "disconnected", "error": str(e)}


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    redis_pool.disconnect()
