"""Low-level DB/Redis infrastructure (registries, pools, connection settings)."""

import logging

from shared_server_libs.infra.config import (
    CATALOG_DB_NAME,
    RANORA_CONFIG_DB_NAME,
    PostgresConnectionSettings,
    RedisSettings,
)
from shared_server_libs.infra.project_session_registry import ProjectSessionRegistry
from shared_server_libs.infra.ranora_config_orm import RanoraConfigBase, TimestampMixin
from shared_server_libs.infra.ranora_config_session_registry import RanoraConfigSessionRegistry
from shared_server_libs.infra.redis_pool import RedisPoolSingleton

logger = logging.getLogger(__name__)

__all__ = [
    "CATALOG_DB_NAME",
    "RANORA_CONFIG_DB_NAME",
    "PostgresConnectionSettings",
    "RedisSettings",
    "ProjectSessionRegistry",
    "RanoraConfigBase",
    "TimestampMixin",
    "RanoraConfigSessionRegistry",
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
    RanoraConfigSessionRegistry.init(pg)
    logger.info("infra initialized")


async def shutdown_infra() -> None:
    await ProjectSessionRegistry.close_all()
    await RanoraConfigSessionRegistry.close_all()
    await RedisPoolSingleton.close()
    logger.info("infra shut down")
