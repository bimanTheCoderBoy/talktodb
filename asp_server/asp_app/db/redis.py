import redis.asyncio as redis

from asp_app.config.acss_config import get_redis_config

REDIS_URL = get_redis_config().redis_url

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)


def get_redis_client():
    return redis_client