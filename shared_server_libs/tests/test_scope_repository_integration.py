from __future__ import annotations

import os

import pytest

from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import (
    UserProjectScopeRepository,
)
from shared_server_libs.db_infra.config import PostgresConnectionSettings
from shared_server_libs.db_infra.user_session_registry import UserSessionRegistry


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_cell_iids_live(integration_db_available: bool):
    if not integration_db_available:
        pytest.skip("DB_HOST not set")

    email = os.getenv("TEST_SCOPE_EMAIL")
    project = os.getenv("TEST_SCOPE_PROJECT")
    if not email or not project:
        pytest.skip("TEST_SCOPE_EMAIL and TEST_SCOPE_PROJECT required for integration test")

    settings = PostgresConnectionSettings.from_env()
    UserSessionRegistry.init(settings)
    repo = UserProjectScopeRepository()
    try:
        iids = await repo.get_cell_iids(project, email)
        assert isinstance(iids, list)
    finally:
        await UserSessionRegistry.close_all()
