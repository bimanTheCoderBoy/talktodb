from __future__ import annotations

import os

import pytest

from shared_server_libs.agent_db_access import get_repository, init_db_stack, shutdown_db_stack
from shared_server_libs.agent_db_access.domain.exception.scope_not_configured import (
    ScopeNotConfiguredError,
)
from shared_server_libs.db_infra.config import PostgresConnectionSettings, RedisSettings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_query_select_one_without_rls(integration_db_available: bool, integration_redis_available: bool):
    if not integration_db_available or not integration_redis_available:
        pytest.skip("DB_HOST and REDIS_URL required")

    project = os.getenv("TEST_SCOPE_PROJECT", "user")
    init_db_stack(
        postgres=PostgresConnectionSettings.from_env(),
        redis=RedisSettings.from_env(),
    )
    try:
        repo = get_repository()
        result = await repo.run_query(
            project,
            "integration@test.com",
            "SELECT 1 AS n",
            use_rls=False,
        )
        assert result.success is True
        assert result.row_count == 1
        assert result.rows[0]["n"] == 1
    finally:
        await shutdown_db_stack()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_query_rls_empty_scope_raises(integration_db_available: bool, integration_redis_available: bool):
    if not integration_db_available or not integration_redis_available:
        pytest.skip("DB_HOST and REDIS_URL required")

    project = os.getenv("TEST_SCOPE_PROJECT")
    if not project:
        pytest.skip("TEST_SCOPE_PROJECT required")

    init_db_stack(
        postgres=PostgresConnectionSettings.from_env(),
        redis=RedisSettings.from_env(),
    )
    try:
        repo = get_repository()
        with pytest.raises(ScopeNotConfiguredError):
            await repo.run_query(
                project,
                "no-scope-user@example.com",
                "SELECT 1",
                use_rls=True,
            )
    finally:
        await shutdown_db_stack()
