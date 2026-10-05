"""Repositories and RLS adapters."""

__all__ = [
    "BaseDatabaseRepository",
    "UserProjectScopeRepository",
    "RLSAdapterHelper",
    "RLSCacheAdapterInvalidator",
    "RLSCacheBase",
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
    if name in ("RLSAdapterHelper", "RLSCacheAdapterInvalidator", "RLSCacheBase"):
        from shared_server_libs.agent_db_access.repositories.rls_cache_adapter_helper import (
            RLSCacheAdapterInvalidator,
            RLSCacheBase,
            RLSAdapterHelper,
        )

        return {
            "RLSAdapterHelper": RLSAdapterHelper,
            "RLSCacheAdapterInvalidator": RLSCacheAdapterInvalidator,
            "RLSCacheBase": RLSCacheBase,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
