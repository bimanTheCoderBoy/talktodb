"""Repositories and RLS adapters."""

__all__ = [
    "BaseDatabaseRepository",
    "UserProjectScopeRepository",
    "RLSAdapterHelper",
    "create_rls_adapter_helper",
]


def __getattr__(name: str):
    if name == "BaseDatabaseRepository":
        from shared_server_libs.agent_db_access.repositories.base_database_repository import (
            BaseDatabaseRepository,
        )

        return BaseDatabaseRepository
    if name == "UserProjectScopeRepository":
        from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import (
            UserProjectScopeRepository,
        )

        return UserProjectScopeRepository
    if name == "RLSAdapterHelper":
        from shared_server_libs.agent_db_access.repositories.rls_adapter_helper import (
            RLSAdapterHelper,
        )

        return RLSAdapterHelper
    if name == "create_rls_adapter_helper":
        from shared_server_libs.agent_db_access.repositories.rls_adapter_helper import (
            create_rls_adapter_helper,
        )

        return create_rls_adapter_helper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
