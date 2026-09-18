from __future__ import annotations

import logging

from redis.asyncio import ConnectionPool, Redis

from shared_server_libs.infra.config import RedisSettings

logger = logging.getLogger(__name__)


class RedisPoolSingleton:
    """Process-wide async Redis connection pool and client."""

    _pool: ConnectionPool | None = None
    _client: Redis | None = None
    _settings: RedisSettings | None = None

    @classmethod
    def init_redis(cls, settings: RedisSettings) -> None:
        if cls._pool is not None:
            raise RuntimeError("Redis pool already initialized")
        cls._settings = settings
        cls._pool = ConnectionPool.from_url(settings.url, decode_responses=True)
        cls._client = Redis(connection_pool=cls._pool)
        logger.info("Redis connection pool initialized")

    @classmethod
    def get_pool(cls) -> ConnectionPool:
        if cls._pool is None:
            raise RuntimeError("Redis pool not initialized; call init_redis first")
        return cls._pool

    @classmethod
    def get_redis(cls) -> Redis:
        if cls._client is None:
            raise RuntimeError("Redis client not initialized; call init_redis first")
        return cls._client

    @classmethod
    def get_settings(cls) -> RedisSettings:
        if cls._settings is None:
            raise RuntimeError("Redis settings not initialized; call init_redis first")
        return cls._settings

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
        if cls._pool is not None:
            await cls._pool.disconnect()
            cls._pool = None
        cls._settings = None
        logger.info("Redis connection pool closed")
