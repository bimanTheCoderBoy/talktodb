from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared_server_libs.agent_db_access.domain.exception.scope_not_configured import (
    ScopeNotConfiguredError,
)
from shared_server_libs.agent_db_access.domain.interface.i_base_database_repository import (
    IBaseDatabaseRepository,
)
from shared_server_libs.agent_db_access.domain.schema.query_result import (
    BulkQueryResult,
    BulkStatementResult,
    QueryResult,
)
from shared_server_libs.agent_db_access.repositories.rls_adapter_helper import RLSAdapterHelper
from shared_server_libs.infra.project_session_registry import ProjectSessionRegistry

logger = logging.getLogger(__name__)


class BaseDatabaseRepository(IBaseDatabaseRepository):
    def __init__(self, rls_helper: RLSAdapterHelper) -> None:
        self._rls_helper = rls_helper

    @asynccontextmanager
    async def get_session(
        self,
        project_name: str,
        email: str,
        *,
        use_rls: bool = True,
    ) -> AsyncIterator[AsyncSession]:
        sessionmaker = await ProjectSessionRegistry.get_sessionmaker(project_name)
        async with sessionmaker() as session:
            async with session.begin():
                if use_rls:
                    iids = await self._rls_helper.get_scoped_cell_iids(project_name, email)
                    if not iids:
                        raise ScopeNotConfiguredError(project_name, email)
                    await session.execute(
                        text("SELECT set_config('app.scope_mode', :mode, true)"),
                        {"mode": "restricted"},
                    )
                    await session.execute(
                        text("SELECT set_config('app.scoped_cell_iids', :iids, true)"),
                        {"iids": json.dumps(iids)},
                    )
                yield session

    async def run_query(
        self,
        project_name: str,
        email: str,
        query: str,
        params: dict[str, Any] | None = None,
        *,
        use_rls: bool = True,
    ) -> QueryResult:
        bound = params or {}
        try:
            async with self.get_session(project_name, email, use_rls=use_rls) as session:
                logger.info("Running query: %s", query)
                logger.info("Parameters: %s", bound)
                result = await session.execute(text(query), bound)
                if not result.returns_rows:
                    return QueryResult(success=True, columns=[], rows=[], row_count=0)

                columns = list(result.keys())
                rows = [dict(row) for row in result.mappings().all()]
                return QueryResult(
                    success=True,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                )
        except ScopeNotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("run_query failed for project=%s", project_name)
            return QueryResult(success=False, error=str(exc))

    async def run_bulk_query(
        self,
        project_name: str,
        email: str,
        statements: list[tuple[str, dict[str, Any] | None]],
        *,
        use_rls: bool = True,
    ) -> BulkQueryResult:
        if not statements:
            return BulkQueryResult(success=True, executed_count=0)

        results: list[BulkStatementResult] = []
        try:
            async with self.get_session(project_name, email, use_rls=use_rls) as session:
                for index, (query, params) in enumerate(statements):
                    try:
                        await session.execute(text(query), params or {})
                        results.append(BulkStatementResult(index=index, success=True))
                    except Exception as exc:
                        results.append(
                            BulkStatementResult(index=index, success=False, error=str(exc))
                        )
                        return BulkQueryResult(
                            success=False,
                            statement_results=results,
                            executed_count=sum(1 for r in results if r.success),
                            error=str(exc),
                        )
            return BulkQueryResult(
                success=True,
                statement_results=results,
                executed_count=len(results),
            )
        except ScopeNotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("run_bulk_query failed for project=%s", project_name)
            return BulkQueryResult(
                success=False,
                statement_results=results,
                executed_count=sum(1 for r in results if r.success),
                error=str(exc),
            )
