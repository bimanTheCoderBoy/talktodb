from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared_server_libs.infra.config import PostgresConnectionSettings

logger = logging.getLogger(__name__)


class ProjectSessionRegistry:
    """Process singleton: lazy async sessionmaker per project database name."""

    _settings: PostgresConnectionSettings | None = None
    _sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {}
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def init(cls, settings: PostgresConnectionSettings) -> None:
        if cls._settings is not None:
            raise RuntimeError("ProjectSessionRegistry already initialized")
        cls._settings = settings

    @classmethod
    def _normalize_key(cls, project_name: str) -> str:
        return project_name.lower().strip()

    @classmethod
    async def get_sessionmaker(cls, project_name: str) -> async_sessionmaker[AsyncSession]:
        if cls._settings is None:
            raise RuntimeError("ProjectSessionRegistry not initialized; call init first")

        key = cls._normalize_key(project_name)
        if key in cls._sessionmakers:
            return cls._sessionmakers[key]

        async with cls._lock:
            if key in cls._sessionmakers:
                return cls._sessionmakers[key]

            engine = create_async_engine(
                cls._settings.get_database_url(key),
                pool_size=cls._settings.pool_size,
                max_overflow=cls._settings.max_overflow,
                pool_pre_ping=True,
                connect_args={"ssl": False},
            )
            sessionmaker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
            )
            cls._sessionmakers[key] = sessionmaker
            logger.info("Created SQLAlchemy sessionmaker for project database: %s", key)
            return sessionmaker

    @classmethod
    async def close_all(cls) -> None:
        async with cls._lock:
            disposed: set[int] = set()
            for sessionmaker in cls._sessionmakers.values():
                engine = sessionmaker.bind
                if engine is None:
                    continue
                engine_id = id(engine)
                if engine_id in disposed:
                    continue
                await engine.dispose()
                disposed.add(engine_id)
            cls._sessionmakers.clear()
            cls._settings = None
        logger.info("All project SQLAlchemy sessionmakers disposed.")
