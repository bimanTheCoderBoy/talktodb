from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from shared_server_libs.agent_db_access.domain.interface.i_base_database_repository import (
    IBaseDatabaseRepository,
)
from shared_server_libs.agent_db_access.repositories.base_database_repository import (
    BaseDatabaseRepository,
)
from shared_server_libs.agent_db_access.repositories.rls_cache_adapter_helper import RLSAdapterHelper, RLSCacheAdapterInvalidator
from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import (
    UserProjectScopeRepository,
)
from shared_server_libs.infra import init_infra, shutdown_infra
from shared_server_libs.infra.config import PostgresConnectionSettings, RedisSettings
from shared_server_libs.infra.project_session_registry import ProjectSessionRegistry
from shared_server_libs.infra.ranora_config_session_registry import RanoraConfigSessionRegistry
from shared_server_libs.infra.redis_pool import RedisPoolSingleton

logger = logging.getLogger(__name__)

_initialized: bool = False


def init_agent_db_access(
    postgres: PostgresConnectionSettings | None = None,
    redis: RedisSettings | None = None,
) -> None:
    global _initialized

    if _initialized:
        raise RuntimeError("Agent DB Access already initialized")

    init_infra(postgres=postgres, redis=redis)
    _initialized = True
    logger.info("Agent DB Access infrastructure initialized")


@asynccontextmanager
async def get_ranora_config_session() -> AsyncIterator[AsyncSession]:
    if not _initialized:
        raise RuntimeError("Agent DB Access not initialized; call init_agent_db_access first")

    session_maker = await RanoraConfigSessionRegistry.get_sessionmaker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_repository(project_name: str) -> AsyncIterator[IBaseDatabaseRepository]:
    if not _initialized:
        raise RuntimeError("Agent DB Access not initialized; call init_agent_db_access first")

    ranora_config_session_maker = await RanoraConfigSessionRegistry.get_sessionmaker()
    project_session_maker = await ProjectSessionRegistry.get_sessionmaker(project_name)
    redis = RedisPoolSingleton.get_redis()
    redis_settings = RedisPoolSingleton.get_settings()
    async with (
        ranora_config_session_maker() as ranora_config_session,
        project_session_maker() as project_session,
    ):
        try:
            user_scope_repository = UserProjectScopeRepository(ranora_config_session)
            rls_helper = RLSAdapterHelper(
                user_scope_repository,
                redis,
                redis_settings,
            )
            repository = BaseDatabaseRepository(rls_helper, project_session)
            yield repository
            await ranora_config_session.commit()
            await project_session.commit()
        except Exception:
            await ranora_config_session.rollback()
            await project_session.rollback()
            raise
          

def get_cache_invalidator() -> RLSCacheAdapterInvalidator:
    if not _initialized:
        raise RuntimeError("Agent DB Access not initialized; call init_agent_db_access first")
    redis = RedisPoolSingleton.get_redis()
    redis_settings = RedisPoolSingleton.get_settings()
    return RLSCacheAdapterInvalidator(redis, redis_settings)

async def shutdown_agent_db_access() -> None:
    global _initialized

    await shutdown_infra()
    _initialized = False
    logger.info("Agent DB Access infrastructure shut down")
