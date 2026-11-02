from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_server_libs.db_access.config import TALKTODB_DB_NAME, PostgresConnectionSettings
from shared_server_libs.db_access.orm import create_db_engine, DbBase

logger = logging.getLogger(__name__)


class DbSessionRegistry:
    """Process singleton: async sessionmaker for the talkToDB Postgres database."""

    _settings: PostgresConnectionSettings | None = None
    _sessionmaker: async_sessionmaker[AsyncSession] | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def init(cls, settings: PostgresConnectionSettings) -> None:
        if cls._settings is not None:
            raise RuntimeError("DbSessionRegistry already initialized")
        cls._settings = settings

    @classmethod
    async def get_sessionmaker(cls) -> async_sessionmaker[AsyncSession]:
        if cls._settings is None:
            raise RuntimeError("DbSessionRegistry not initialized; call init_db_access first")

        if cls._sessionmaker is not None:
            return cls._sessionmaker

        async with cls._lock:
            if cls._sessionmaker is not None:
                return cls._sessionmaker

            engine = create_db_engine(cls._settings)

            # Idempotent: creates missing tables only. App must import ORM models on DbBase first.
            async with engine.begin() as conn:
                await conn.run_sync(DbBase.metadata.create_all)
            logger.info("Ensured ORM tables in talkToDB database: %s", TALKTODB_DB_NAME)

            cls._sessionmaker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
            )
            logger.info(
                "Created SQLAlchemy sessionmaker for talkToDB database: %s",
                TALKTODB_DB_NAME,
            )
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
        logger.info("talkToDB database SQLAlchemy sessionmaker disposed.")
