from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from shared_server_libs.db_access.config import PostgresConnectionSettings
from shared_server_libs.db_access.session_registry import DbSessionRegistry

logger = logging.getLogger(__name__)

_initialized: bool = False


def init_db_access(postgres: PostgresConnectionSettings | None = None) -> None:
    global _initialized

    if _initialized:
        raise RuntimeError("DB access already initialized")

    settings = postgres or PostgresConnectionSettings.from_env()
    DbSessionRegistry.init(settings)
    _initialized = True
    logger.info("talkToDB DB access initialized")


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    if not _initialized:
        raise RuntimeError("DB access not initialized; call init_db_access first")

    session_maker = await DbSessionRegistry.get_sessionmaker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def prepare_db() -> None:
    """Create engine, run create_all, and cache the sessionmaker.

    Import all DbBase ORM model modules before calling this.
    """
    await DbSessionRegistry.get_sessionmaker()



async def shutdown_db_access() -> None:
    global _initialized

    await DbSessionRegistry.close_all()
    _initialized = False
    logger.info("talkToDB DB access shut down")
