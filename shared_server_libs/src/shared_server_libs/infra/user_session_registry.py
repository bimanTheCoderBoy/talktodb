from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared_server_libs.infra.config import USER_DB_NAME, PostgresConnectionSettings

logger = logging.getLogger(__name__)


class UserSessionRegistry:
    """Process singleton: single async sessionmaker for the fixed user database."""

    _settings: PostgresConnectionSettings | None = None
    _sessionmaker: async_sessionmaker[AsyncSession] | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def init(cls, settings: PostgresConnectionSettings) -> None:
        if cls._settings is not None:
            raise RuntimeError("UserSessionRegistry already initialized")
        cls._settings = settings

    @classmethod
    async def get_sessionmaker(cls) -> async_sessionmaker[AsyncSession]:
        if cls._settings is None:
            raise RuntimeError("UserSessionRegistry not initialized; call init first")

        if cls._sessionmaker is not None:
            return cls._sessionmaker

        async with cls._lock:
            if cls._sessionmaker is not None:
                return cls._sessionmaker

            engine = create_async_engine(
                cls._settings.get_database_url(USER_DB_NAME),
                pool_size=cls._settings.pool_size,
                max_overflow=cls._settings.max_overflow,
                pool_pre_ping=True,
                connect_args={"ssl": False},
            )
            cls._sessionmaker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
            )
            logger.info("Created SQLAlchemy sessionmaker for user database: %s", USER_DB_NAME)
            return cls._sessionmaker

    @classmethod
    async def close_all(cls) -> None:
        async with cls._lock:
            if cls._sessionmaker is not None:
                engine = cls._sessionmaker.bind
                if engine is not None:
                    await engine.dispose()
            cls._sessionmaker = None
            cls._settings = None
        logger.info("User database SQLAlchemy sessionmaker disposed.")
