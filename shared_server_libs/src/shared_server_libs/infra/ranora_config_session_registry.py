from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_server_libs.infra.config import RANORA_CONFIG_DB_NAME, PostgresConnectionSettings
from shared_server_libs.infra.ranora_config_orm import create_ranora_config_engine

logger = logging.getLogger(__name__)


class RanoraConfigSessionRegistry:
    """Process singleton: single async sessionmaker for the fixed ranora_config database."""

    _settings: PostgresConnectionSettings | None = None
    _sessionmaker: async_sessionmaker[AsyncSession] | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def init(cls, settings: PostgresConnectionSettings) -> None:
        if cls._settings is not None:
            raise RuntimeError("RanoraConfigSessionRegistry already initialized")
        cls._settings = settings

    @classmethod
    async def get_sessionmaker(cls) -> async_sessionmaker[AsyncSession]:
        if cls._settings is None:
            raise RuntimeError("RanoraConfigSessionRegistry not initialized; call init first")

        if cls._sessionmaker is not None:
            return cls._sessionmaker

        async with cls._lock:
            if cls._sessionmaker is not None:
                return cls._sessionmaker

            engine = create_ranora_config_engine(cls._settings)
            cls._sessionmaker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
            )
            logger.info(
                "Created SQLAlchemy sessionmaker for ranora_config database: %s",
                RANORA_CONFIG_DB_NAME,
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
        logger.info("ranora_config database SQLAlchemy sessionmaker disposed.")
