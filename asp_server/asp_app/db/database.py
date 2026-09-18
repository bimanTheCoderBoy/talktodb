import asyncio
from contextlib import asynccontextmanager
import json
from typing import AsyncGenerator, List
from fastapi import Header
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from asp_app.config.acss_config import get_database_config
from asp_app.db.models import Base
from sqlalchemy import text
import logging
logger = logging.getLogger(__name__)

USER_DB_NAME = "user"

class EngineRegistry:
    """
    Registry for managing database engine instances.
    Implements singleton pattern for each database connection.
    """
    _engines = {}
    _lock = asyncio.Lock()

    @classmethod
    async def get_engine(cls, project_name: str):
        """
        Get or create an async engine for the specified project database.
        
        Args:
            project_name: Name of the database/project
            
        Returns:
            AsyncEngine instance
        """
        key = project_name.lower()

        if key in cls._engines:
            return cls._engines[key]

        async with cls._lock:
            if key in cls._engines:
                return cls._engines[key]

            db_config = get_database_config()
            engine = create_async_engine(
                db_config.get_database_url(key),
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_pre_ping=True,
            )
            logger.info(f"[GET ENGINE] Getting engine for project: {key}")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
                # Check for missing columns and add them if necessary
                # This is a simple way to handle schema updates without Alembic
                from sqlalchemy import text
                try:
                    # Add execution_status_state if it's missing
                    await conn.execute(text("ALTER TABLE acss_sessions ADD COLUMN IF NOT EXISTS execution_status_state JSONB DEFAULT '{}'::jsonb"))
                    # Add setup_state if it's missing (though it likely exists)
                    await conn.execute(text("ALTER TABLE acss_sessions ADD COLUMN IF NOT EXISTS setup_state JSONB DEFAULT '{}'::jsonb"))
                except Exception as e:
                    print(f"Warning: Could not add columns to acss_sessions: {e}")

                # --- acss_candidate_evaluation patches ---
                try:
                    # Ensure goal_value is DOUBLE PRECISION (may have been created as integer)
                    await conn.execute(text(
                        "ALTER TABLE acss_candidate_evaluation "
                        "ALTER COLUMN goal_value TYPE DOUBLE PRECISION "
                        "USING goal_value::double precision"
                    ))
                except Exception as e:
                    # Column may already be the correct type or table may not exist yet
                    print(f"Warning: Could not alter goal_value type: {e}")

                try:
                    # Add result_details JSONB column if missing
                    await conn.execute(text(
                        "ALTER TABLE acss_candidate_evaluation "
                        "ADD COLUMN IF NOT EXISTS result_details JSONB DEFAULT '{}'::jsonb"
                    ))
                except Exception as e:
                    print(f"Warning: Could not add result_details column: {e}")
            cls._engines[key] = engine
            return engine

    @classmethod
    async def get_sessionmaker(cls, project_name: str) -> async_sessionmaker[AsyncSession]:
        """
        Get an async session maker for the specified project database.
        
        Args:
            project_name: Name of the database/project
            
        Returns:
            async_sessionmaker instance
        """
        engine = await cls.get_engine(project_name)
        return async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession
        )

    @classmethod
    async def close_all(cls):
        """Close all database connections."""
        for engine in cls._engines.values():
            await engine.dispose()
        cls._engines.clear()

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

async def find_scope_cell_iids(project_name: str, user_email: str) -> list[str]:
    async with user_db_session() as session:
        try:
            result = await session.execute(
                text("SELECT cell_iids FROM user_project_config WHERE email = :email AND project_name = :project"),
                {"email": user_email, "project": project_name},
            )
            
            cell_iids = result.scalar_one_or_none()

            if cell_iids is None:
                return []

            return list(cell_iids)
        except Exception as e:
            logger.error(f"Error finding scope cell iids: {e}")
            return []

async def get_rls_db_session(
    x_project_name: str = Header(..., description="Project name for database connection"),
    x_user_email: str = Header(None, description="User email for RLS scoped database connection"),
) -> AsyncGenerator[AsyncSession, None]:
    if x_user_email:
        scoped_cell_iids = await find_scope_cell_iids(x_project_name, x_user_email)
        mode = "restricted" if scoped_cell_iids else "unrestricted"
    else:
        scoped_cell_iids = []
        mode = "unrestricted"

    sessionmaker = await EngineRegistry.get_sessionmaker(x_project_name)
    async with sessionmaker() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.scope_mode', :mode, true)"),
                {"mode": mode},
            )
            await session.execute(
                text("SELECT set_config('app.scoped_cell_iids', :iids, true)"),
                {"iids": json.dumps(scoped_cell_iids)},
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session(x_project_name: str = Header(..., description="Project name for database connection")) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database sessions in FastAPI routes.
    
    The project name is retrieved from the 'x-project-name' HTTP header.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    sessionmaker = await EngineRegistry.get_sessionmaker(x_project_name)
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
