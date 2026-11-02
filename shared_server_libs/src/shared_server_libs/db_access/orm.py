from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared_server_libs.db_access.config import PostgresConnectionSettings, TALKTODB_DB_NAME


class DbBase(DeclarativeBase):
    """Declarative base for ORM models stored in the talkToDB Postgres database."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def create_db_engine(settings: PostgresConnectionSettings) -> AsyncEngine:
    return create_async_engine(
        settings.get_database_url(TALKTODB_DB_NAME),
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        connect_args={"ssl": False},
    )
