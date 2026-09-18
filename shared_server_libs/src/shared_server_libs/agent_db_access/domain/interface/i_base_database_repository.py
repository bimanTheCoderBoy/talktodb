from __future__ import annotations

from typing import Any, Protocol

from shared_server_libs.agent_db_access.domain.schema.query_result import BulkQueryResult, QueryResult


class IBaseDatabaseRepository(Protocol):
    async def run_query(
        self,
        project_name: str,
        email: str,
        query: str,
        params: dict[str, Any] | None = None,
        *,
        use_rls: bool = True,
    ) -> QueryResult: ...

    async def run_bulk_query(
        self,
        project_name: str,
        email: str,
        statements: list[tuple[str, dict[str, Any] | None]],
        *,
        use_rls: bool = True,
    ) -> BulkQueryResult: ...
