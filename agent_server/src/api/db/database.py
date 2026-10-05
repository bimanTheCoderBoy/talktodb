import asyncio
import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pydantic import BaseModel, Field
from typing import Annotated
from functools import lru_cache

logger = logging.getLogger(__name__)

# Fixed database name for user-level configuration (ranora_config)
USER_DB_NAME = os.getenv("RANORA_CONFIG_DB_NAME", "ranora_config")


class DatabaseConfig(BaseModel):
    """Database connection configuration (reads from same env vars as the agent)."""
    db_host: Annotated[str, Field(default=os.getenv("DB_HOST", "localhost"))]
    db_port: Annotated[int, Field(default=int(os.getenv("DB_PORT", "5432")))]
    db_user: Annotated[str, Field(default=os.getenv("API_DB_USER", "csv_user"))]
    db_password: Annotated[str, Field(default=os.getenv("API_DB_PASSWORD", "csv_password"))]
    pool_size: Annotated[int, Field(default=int(os.getenv("DB_POOL_SIZE", "5")))]
    max_overflow: Annotated[int, Field(default=int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")))]

    def get_database_url(self, db_name: str) -> str:
        """Generate async database URL for a specific database."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{db_name}"
        )


@lru_cache()
def get_database_config() -> DatabaseConfig:
    """Get cached database configuration."""
    return DatabaseConfig()


class EngineRegistry:
    """
    Registry for managing async SQLAlchemy engine instances.
    Lazily creates one engine per project/database name.
    """
    _engines: dict = {}
    _lock = asyncio.Lock()

    @classmethod
    async def get_engine(cls, project_name: str):
        key = project_name.lower().strip()

        if key in cls._engines:
            return cls._engines[key]

        async with cls._lock:
            # Double-check after acquiring lock
            if key in cls._engines:
                return cls._engines[key]

            db_config = get_database_config()
            engine = create_async_engine(
                db_config.get_database_url(key),
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_pre_ping=True,
                connect_args={"ssl": False}
            )

            # Auto-create tables for the "user" database (when creating its engine)
            if key == USER_DB_NAME:
                from api.db.models import Base
                import database_context_retrieval.domain.entity  # noqa: F401 - register catalog ORM
                from shared_server_libs.infra.ranora_config_orm import RanoraConfigBase

                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    await conn.run_sync(RanoraConfigBase.metadata.create_all)
                    await conn.execute(
                        text(
                            "ALTER TABLE user_audit_custom_rule "
                            "ADD COLUMN IF NOT EXISTS column_checks JSONB DEFAULT '[]'::jsonb"
                        )
                    )
                logger.info("Created/verified tables in %r database.", USER_DB_NAME)

            cls._engines[key] = engine
            logger.info(f"Created SQLAlchemy engine for project: {key}")
            return engine

    @classmethod
    async def get_sessionmaker(cls, project_name: str) -> async_sessionmaker[AsyncSession]:
        engine = await cls.get_engine(project_name)
        return async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

    @classmethod
    async def close_all(cls):
        """Dispose all engines (call on app shutdown)."""
        for engine in cls._engines.values():
            await engine.dispose()
        cls._engines.clear()
        logger.info("All SQLAlchemy engines disposed.")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

@asynccontextmanager
async def user_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides an AsyncSession for the fixed "user" database.

    Use this in non-FastAPI code paths (e.g. LangGraph nodes) where `async with ...`
    is preferred over FastAPI's yield-style dependency injection.
    """
    sessionmaker = await EngineRegistry.get_sessionmaker(USER_DB_NAME)
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            logger.exception("Unhandled exception in user_db_session")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session(
    x_project_name: str = Header(..., description="Project name (database name)")
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession for the project
    specified by the ``x-project-name`` HTTP header.
    """
    sessionmaker = await EngineRegistry.get_sessionmaker(x_project_name)
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            logger.exception("Unhandled exception in get_db_session")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_user_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession for the fixed
    "user" database (stores user_project_config, etc.).
    """
    async with user_db_session() as session:
        yield session
