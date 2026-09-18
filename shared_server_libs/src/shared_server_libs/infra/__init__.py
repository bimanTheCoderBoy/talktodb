"""Low-level DB/Redis infrastructure (registries, pools, connection settings)."""

import logging

from shared_server_libs.infra.config import (
    USER_DB_NAME,
    PostgresConnectionSettings,
    RedisSettings,
)
from shared_server_libs.infra.project_session_registry import ProjectSessionRegistry
from shared_server_libs.infra.redis_pool import RedisPoolSingleton
from shared_server_libs.infra.user_session_registry import UserSessionRegistry

logger = logging.getLogger(__name__)

__all__ = [
    "USER_DB_NAME",
    "PostgresConnectionSettings",
    "RedisSettings",
    "ProjectSessionRegistry",
    "UserSessionRegistry",
    "RedisPoolSingleton",
    "init_infra",
    "shutdown_infra",
]


def init_infra(
    postgres: PostgresConnectionSettings | None = None,
    redis: RedisSettings | None = None,
) -> None:
    pg = postgres or PostgresConnectionSettings.from_env()
    rd = redis or RedisSettings.from_env()
    RedisPoolSingleton.init_redis(rd)
    ProjectSessionRegistry.init(pg)
    UserSessionRegistry.init(pg)
    logger.info("infra initialized")


async def shutdown_infra() -> None:
    await ProjectSessionRegistry.close_all()
    await UserSessionRegistry.close_all()
    await RedisPoolSingleton.close()
    logger.info("infra shut down")
