"""Agent-facing database access (RLS queries, scope cache, repository API)."""

from shared_server_libs.agent_db_access.bootstrap import (
    get_cache_invalidator,
    get_ranora_config_session,
    get_repository,
    init_agent_db_access,
    shutdown_agent_db_access,
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

# Backward-compatible aliases
init_db_stack = init_agent_db_access
shutdown_db_stack = shutdown_agent_db_access

__all__ = [
    "ScopeNotConfiguredError",
    "IBaseDatabaseRepository",
    "QueryResult",
    "BulkQueryResult",
    "BulkStatementResult",
    "init_agent_db_access",
    "shutdown_agent_db_access",
    "init_db_stack",
    "shutdown_db_stack",
    "get_repository",
    "get_ranora_config_session",
    "get_cache_invalidator",
]
