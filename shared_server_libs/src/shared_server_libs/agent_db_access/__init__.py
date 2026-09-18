"""Agent-facing database access (RLS queries, scope cache, repository API)."""

from shared_server_libs.agent_db_access.bootstrap import (
    get_repository,
    get_rls_adapter_helper,
    init_db_stack,
    shutdown_db_stack,
)
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

__all__ = [
    "ScopeNotConfiguredError",
    "IBaseDatabaseRepository",
    "QueryResult",
    "BulkQueryResult",
    "BulkStatementResult",
    "init_db_stack",
    "get_repository",
    "get_rls_adapter_helper",
    "shutdown_db_stack",
]
