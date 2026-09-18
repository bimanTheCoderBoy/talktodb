from __future__ import annotations

import logging

from shared_server_libs.agent_db_access.domain.interface.i_base_database_repository import (
    IBaseDatabaseRepository,
)
from shared_server_libs.agent_db_access.repositories.base_database_repository import (
    BaseDatabaseRepository,
)
from shared_server_libs.agent_db_access.repositories.rls_adapter_helper import (
    RLSAdapterHelper,
    create_rls_adapter_helper,
)
from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import (
    UserProjectScopeRepository,
)
from shared_server_libs.infra import init_infra, shutdown_infra    
from shared_server_libs.infra.config import PostgresConnectionSettings, RedisSettings

logger = logging.getLogger(__name__)

_scope_repository: UserProjectScopeRepository | None = None
_rls_helper: RLSAdapterHelper | None = None
_repository: BaseDatabaseRepository | None = None
_initialized: bool = False


def init_agent_db_access(
    postgres: PostgresConnectionSettings | None = None,
    redis: RedisSettings | None = None,
) -> None:
    global _scope_repository, _rls_helper, _repository, _initialized

    if _initialized:
        raise RuntimeError("Agent DB Access already initialized")

    init_infra(postgres=postgres, redis=redis)

    _scope_repository = UserProjectScopeRepository()
    _rls_helper = create_rls_adapter_helper(_scope_repository)
    _repository = BaseDatabaseRepository(_rls_helper)
    _initialized = True
    logger.info("Agent DB Access infrastructure initialized")


def get_repository() -> IBaseDatabaseRepository:
    if _repository is None:
        raise RuntimeError("Agent DB Access not initialized; call init_agent_db_access first")
    return _repository


def get_rls_adapter_helper() -> RLSAdapterHelper:
    if _rls_helper is None:
        raise RuntimeError("Agent DB Access not initialized; call init_agent_db_access first")
    return _rls_helper


async def shutdown_agent_db_access() -> None:
    global _scope_repository, _rls_helper, _repository, _initialized

    await shutdown_infra()

    _scope_repository = None
    _rls_helper = None
    _repository = None
    _initialized = False
    logger.info("Agent DB Access infrastructure shut down")
