from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from computer.config.logger import get_computer_logger
from database_context_retrieval.domain.exception.catalog_column import CatalogColumnError
from database_context_retrieval.domain.exception.catalog_context_search import (
    CatalogContextSearchError,
)
from database_context_retrieval.domain.exception.catalog_relation import CatalogRelationError
from database_context_retrieval.domain.exception.catalog_table import CatalogTableError
from database_context_retrieval.domain.schema.catalog_context_search import CatalogContextSearchResult
from database_context_retrieval.domain.schema.catalog_column import CatalogColumnLookupResult
from database_context_retrieval.domain.schema.catalog_relation import CatalogRelationLookupResult
from database_context_retrieval.domain.schema.catalog_table import CatalogTableLookupResult
from database_context_retrieval.repositories.catalog_column_repository import CatalogColumnRepository
from database_context_retrieval.repositories.catalog_relation_repository import CatalogRelationRepository
from database_context_retrieval.repositories.catalog_table_repository import CatalogTableRepository
from database_context_retrieval.services.catalog_column_service import CatalogColumnService
from database_context_retrieval.services.catalog_context_search_service import (
    CatalogContextSearchService,
)
from database_context_retrieval.services.catalog_relation_service import CatalogRelationService
from database_context_retrieval.services.catalog_table_service import CatalogTableService
from shared_server_libs.agent_db_access.bootstrap import get_ranora_config_session, get_repository
from shared_server_libs.agent_db_access.domain.exception.scope_not_configured import (
    ScopeNotConfiguredError,
)
from shared_server_libs.agent_db_access.domain.schema.query_result import QueryResult

logger = get_computer_logger(__name__)

_RUN_DB_QUERY_TOOL_CACHE: dict[tuple[str, str], BaseTool] = {}


class GetDatabaseColumnInput(BaseModel):
    table_name: str = Field(description="Exact catalog table name that owns the column.")
    column_name: str = Field(description="Exact column name within that table.")


class GetDatabaseRelationInput(BaseModel):
    table_a: str = Field(description="First table name in the semantic catalog.")
    table_b: str = Field(description="Second table name; relations are returned in either direction.")


class SearchDatabaseContextInput(BaseModel):
    query: str = Field(
        description="Natural-language question or keywords to find relevant catalog columns and tables.",
    )


class GetDatabaseTableInput(BaseModel):
    table_name: str = Field(description="Exact name of the table in the semantic catalog.")
    column_limit: int | None = Field(
        default=15,
        description="Maximum number of columns to return in this page (default 15).",
    )
    column_offset: int | None = Field(
        default=0,
        description="Number of columns to skip for pagination (default 0).",
    )


class RunDbQueryInput(BaseModel):
    query: str = Field(
        description="SQL to run against the current project database. Prefer read-only SELECT queries.",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Optional named bind parameters for the query.",
    )


@tool("get_database_table", args_schema=GetDatabaseTableInput, parse_docstring=False)
async def get_database_table(
    table_name: str,
    column_limit: int | None = 15,
    column_offset: int | None = 0,
) -> str:
    """
    Look up semantic catalog metadata for a database table.

    Use before writing SQL when you need table description, primary keys, relationships,
    or column meanings. If the table is not found, similar catalog names may be returned.
    Paginate columns with column_offset when total_column_count exceeds the returned columns.
    """
    queried_name = table_name.strip()
    logger.info("[DB_CONTEXT] get_database_table table_name=%r", table_name)
    try:
        async with get_ranora_config_session() as session:
            service = CatalogTableService(CatalogTableRepository(session))
            result = await service.get_table_info(
                table_name,
                column_limit=column_limit,
                column_offset=column_offset,
            )
    except CatalogTableError as exc:
        logger.warning("[DB_CONTEXT] get_database_table failed: %s", exc)
        result = CatalogTableLookupResult.failure(queried_name, str(exc))
    except RuntimeError as exc:
        logger.error("[DB_CONTEXT] get_database_table infrastructure error", exc_info=True)
        result = CatalogTableLookupResult.failure(queried_name, str(exc))
    except Exception as exc:
        logger.exception("[DB_CONTEXT] get_database_table unexpected error")
        result = CatalogTableLookupResult.failure(
            queried_name,
            f"Unexpected error during catalog lookup: {exc}",
        )
    return result.model_dump_json()


@tool("get_database_column", args_schema=GetDatabaseColumnInput, parse_docstring=False)
async def get_database_column(
    table_name: str,
    column_name: str,
) -> str:
    """
    Look up semantic catalog metadata for a single column.

    Use when you need data type, description, or example use cases for one column.
    If the column is not found, similar catalog columns (table.column) may be returned.
    """
    queried_table = table_name.strip()
    queried_column = column_name.strip()
    logger.info(
        "[DB_CONTEXT] get_database_column table=%r column=%r",
        table_name,
        column_name,
    )
    try:
        async with get_ranora_config_session() as session:
            service = CatalogColumnService(CatalogColumnRepository(session))
            result = await service.get_column_info(table_name, column_name)
    except CatalogColumnError as exc:
        logger.warning("[DB_CONTEXT] get_database_column failed: %s", exc)
        result = CatalogColumnLookupResult.failure(queried_table, queried_column, str(exc))
    except RuntimeError as exc:
        logger.error("[DB_CONTEXT] get_database_column infrastructure error", exc_info=True)
        result = CatalogColumnLookupResult.failure(queried_table, queried_column, str(exc))
    except Exception as exc:
        logger.exception("[DB_CONTEXT] get_database_column unexpected error")
        result = CatalogColumnLookupResult.failure(
            queried_table,
            queried_column,
            f"Unexpected error during column lookup: {exc}",
        )
    return result.model_dump_json()


@tool("get_database_relation", args_schema=GetDatabaseRelationInput, parse_docstring=False)
async def get_database_relation(
    table_a: str,
    table_b: str,
) -> str:
    """
    Look up semantic catalog join relationships between two tables.

    Returns relations in either direction (source/target). Use when planning JOINs
    or explaining how two catalog tables connect. If none match, similar catalog
    table names may be returned for each input table.
    """
    queried_a = table_a.strip()
    queried_b = table_b.strip()
    logger.info(
        "[DB_CONTEXT] get_database_relation table_a=%r table_b=%r",
        table_a,
        table_b,
    )
    try:
        async with get_ranora_config_session() as session:
            service = CatalogRelationService(CatalogRelationRepository(session))
            result = await service.get_relation_info(table_a=table_a, table_b=table_b)
    except CatalogRelationError as exc:
        logger.warning("[DB_CONTEXT] get_database_relation failed: %s", exc)
        result = CatalogRelationLookupResult.failure(
            error=str(exc),
            queried_table_a=queried_a,
            queried_table_b=queried_b,
        )
    except RuntimeError as exc:
        logger.error("[DB_CONTEXT] get_database_relation infrastructure error", exc_info=True)
        result = CatalogRelationLookupResult.failure(
            error=str(exc),
            queried_table_a=queried_a,
            queried_table_b=queried_b,
        )
    except Exception as exc:
        logger.exception("[DB_CONTEXT] get_database_relation unexpected error")
        result = CatalogRelationLookupResult.failure(
            error=f"Unexpected error during relation lookup: {exc}",
            queried_table_a=queried_a,
            queried_table_b=queried_b,
        )
    return result.model_dump_json()


@tool("search_database_context", args_schema=SearchDatabaseContextInput, parse_docstring=False)
async def search_database_context(query: str) -> str:
    """
    Search the semantic catalog by meaning (hybrid retrieval), then enrich top tables.

    Use when the user question does not map to a known table or column name. Returns
    ranked column hits from retrieval plus per-table catalog metadata (description,
    relationships). Column details come from retrieval hits, not paginated table lookup.
    Prefer get_database_table for exact table names.
    """
    normalized_query = query.strip()
    logger.info("[DB_CONTEXT] search_database_context query=%r", query)
    try:
        async with get_ranora_config_session() as session:
            table_service = CatalogTableService(CatalogTableRepository(session))
            service = CatalogContextSearchService(table_service)
            result = await service.search(query)
    except CatalogContextSearchError as exc:
        logger.warning("[DB_CONTEXT] search_database_context failed: %s", exc)
        result = CatalogContextSearchResult.failure(normalized_query, str(exc))
    except RuntimeError as exc:
        logger.error("[DB_CONTEXT] search_database_context infrastructure error", exc_info=True)
        result = CatalogContextSearchResult.failure(normalized_query, str(exc))
    except Exception as exc:
        logger.exception("[DB_CONTEXT] search_database_context unexpected error")
        result = CatalogContextSearchResult.failure(
            normalized_query,
            f"Unexpected error during catalog context search: {exc}",
        )
    return result.model_dump_json()


CATALOG_CONTEXT_TOOLS: list[BaseTool] = [
    get_database_table,
    get_database_column,
    get_database_relation,
    search_database_context,
]


def _make_run_db_query_tool(project_name: str, user_email: str) -> BaseTool:
    normalized_project = project_name.strip()
    normalized_email = user_email.strip()

    @tool("run_db_query", args_schema=RunDbQueryInput, parse_docstring=False)
    async def run_db_query(
        query: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """
        Execute SQL on the user's current project database with row-level scope applied.

        Use after get_database_table when you need actual data. Pass named parameters via params
        when the SQL uses bind placeholders. Returns columns, rows, and row_count as JSON.
        """
        logger.info(
            "[DB_CONTEXT] run_db_query project=%r email=%r",
            normalized_project,
            normalized_email,
        )
        try:
            async with get_repository(normalized_project) as repository:
                result = await repository.run_query(
                    normalized_project,
                    normalized_email,
                    query,
                    params,
                    use_rls=True,
                )
        except ScopeNotConfiguredError as exc:
            logger.warning("[DB_CONTEXT] run_db_query scope not configured: %s", exc)
            result = QueryResult(success=False, error=str(exc))
        except Exception as exc:
            logger.exception("[DB_CONTEXT] run_db_query unexpected error")
            result = QueryResult(success=False, error=f"Unexpected error during query execution: {exc}")
        return result.model_dump_json()

    return run_db_query


def get_run_db_query_tool(project_name: str, user_email: str) -> BaseTool:
    if not project_name or not project_name.strip():
        raise ValueError("project_name is required for run_db_query")
    if not user_email or not user_email.strip():
        raise ValueError("user_email is required for run_db_query")

    key = (project_name.strip().lower(), user_email.strip().lower())
    if key not in _RUN_DB_QUERY_TOOL_CACHE:
        _RUN_DB_QUERY_TOOL_CACHE[key] = _make_run_db_query_tool(project_name, user_email)
    return _RUN_DB_QUERY_TOOL_CACHE[key]


def get_database_context_tools(project_name: str, user_email: str) -> list[BaseTool]:
    return [
        *CATALOG_CONTEXT_TOOLS,
        get_run_db_query_tool(project_name, user_email),
    ]
