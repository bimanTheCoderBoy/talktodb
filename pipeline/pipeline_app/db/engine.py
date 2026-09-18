from contextlib import asynccontextmanager, contextmanager
import os
import re
from typing import AsyncIterator, Iterator, Optional
from urllib.parse import urlparse

import asyncpg
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import Session, sessionmaker
from pipeline_app.db.models import Base
from pipeline_app.db.security import (
    ensure_extensions,
    ensure_grants,
    ensure_rls_policies,
    ensure_performance_indexes,
)
from pipeline_app.core.config import PipelineConfig as Config
from pipeline_app.core.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

_VALID_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class DatabaseManager:
    def __init__(
        self, 
        db_url: str,
        rls_user: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ):
        self._db_url = db_url
        self._rls_user = rls_user
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_pre_ping = pool_pre_ping
        self._pool_recycle = pool_recycle

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._sync_engine: Optional[Engine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._provisioned = False
        

    @classmethod
    def from_config(cls, config) -> "DatabaseManager":
        db = config.db
        db_name = config.project_name.lower().strip()
        url = f"postgresql+asyncpg://{db.user}:{db.password}@{db.host}:{db.port}/{db_name}"
        return cls(url, db.rls_user, pool_size=db.pool_size, max_overflow=db.max_overflow)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._db_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_pre_ping=self._pool_pre_ping,
                pool_recycle=self._pool_recycle,
            )
            self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)
        return self._engine
    
    @property
    def sync_engine(self) -> Engine:
        if self._sync_engine is None:
            sync_url = self._db_url.replace("+asyncpg", "+psycopg2")
            self._sync_engine = create_engine(
                sync_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_pre_ping=self._pool_pre_ping,
                pool_recycle=self._pool_recycle,
            )
            self._sync_session_factory = sessionmaker(bind=self._sync_engine)
        return self._sync_engine
    
    @property
    def pool_size(self) -> int:
        try:
            return self._engine.pool.size()
        except Exception:
            return self._pool_size
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is None:
            _ = self.engine
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    @contextmanager
    def sync_session(self) -> Iterator[Session]:
        if self._sync_session_factory is None:
            _ = self.sync_engine
        session = self._sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def unmanaged_session(self) -> AsyncSession:
        if self._session_factory is None:
            _ = self.engine
        return self._session_factory()

    async def _ensure_rls_role_exists(self) -> None:
        if not self._rls_user or not _VALID_IDENT.fullmatch(self._rls_user):
            return

        parsed = urlparse(self._db_url)
        rls_pw = Config.from_env().rls_password

        conn = await asyncpg.connect(
            host=parsed.hostname or Config.db.host,
            port=parsed.port or Config.db.port,
            user=parsed.username or Config.db.user,
            password=parsed.password or Config.db.password,
            database="postgres", ssl=False, passfile=None,
        )
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = $1",
                self._rls_user,
            )
            if not exists:
                await conn.execute(
                    f'CREATE ROLE "{self._rls_user}" LOGIN PASSWORD \'{rls_pw}\''
                )
        finally:
            await conn.close()
    
    async def _ensure_database_exists(self) -> None:
        parsed = urlparse(self._db_url)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            return

        host = parsed.hostname or Config.db.host
        port = parsed.port or Config.db.port
        admin_user = parsed.username or Config.db.user
        admin_pw = parsed.password or Config.db.password

        try:
            test_conn = await asyncpg.connect(
                host=host, port=port, user=admin_user, password=admin_pw,
                database=db_name, ssl=False, passfile=None,
            )
            await test_conn.close()
        except asyncpg.InvalidCatalogNameError:
            admin_conn = await asyncpg.connect(
                host=host, port=port, user=admin_user, password=admin_pw,
                database="postgres", ssl=False, passfile=None,
            )
            try:
                exists = await admin_conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1", db_name,
                )
                if not exists:
                    await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
                    if self._rls_user and _VALID_IDENT.fullmatch(self._rls_user):
                        await admin_conn.execute(
                            f'GRANT CONNECT ON DATABASE "{db_name}" TO "{self._rls_user}"'
                        )
            finally:
                await admin_conn.close()

    async def provision(
        self,
        *,
        create_db: bool = True,
        setup_rls: bool = True,
        create_indexes: bool = True,
    ) -> None:
        """
            One-time database provisioning. Idempotent -- skips if already done.
        """
        if self._provisioned:
            return

        if create_db:
            await self._ensure_rls_role_exists()
            await self._ensure_database_exists()

        async with self.engine.begin() as conn:
            await ensure_extensions(conn)
            await conn.run_sync(Base.metadata.create_all)
            if setup_rls:
                await ensure_rls_policies(conn)
                await ensure_grants(conn, self._rls_user)
            if create_indexes:
                await ensure_performance_indexes(conn)

        self._provisioned = True
        logger.info("Database provisioned: %s", self._safe_url)

    async def dispose(self) -> None:
        """Shut down the engine and release the connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.debug("Engine disposed: %s", self._safe_url)
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            self._sync_session_factory = None
            logger.debug("Sync engine disposed: %s", self._safe_url)
        self._provisioned = False

    async def __aenter__(self) -> "DatabaseManager":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.dispose()

    @property
    def _safe_url(self) -> str:
        """URL with password masked for logging."""
        parsed = urlparse(self._db_url)
        if parsed.password:
            return self._db_url.replace(f":{parsed.password}@", ":***@", 1)
        return self._db_url
