from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared_server_libs.agent_db_access.domain.exception.scope_not_configured import (
    ScopeNotConfiguredError,
)
from shared_server_libs.agent_db_access.repositories.base_database_repository import (
    BaseDatabaseRepository,
)


def _session_stack(session: AsyncMock) -> MagicMock:
    begin_cm = MagicMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=begin_cm)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    sessionmaker = MagicMock(return_value=session_cm)
    return sessionmaker


@pytest.mark.asyncio
async def test_run_query_raises_when_rls_scope_empty():
    rls_helper = AsyncMock()
    rls_helper.get_scoped_cell_iids = AsyncMock(return_value=[])

    session = AsyncMock()
    sessionmaker = _session_stack(session)

    with patch(
        "shared_server_libs.agent_db_access.repositories.base_database_repository.ProjectSessionRegistry.get_sessionmaker",
        new=AsyncMock(return_value=sessionmaker),
    ):
        repo = BaseDatabaseRepository(rls_helper)
        with pytest.raises(ScopeNotConfiguredError):
            await repo.run_query("proj", "u@e.com", "SELECT 1", use_rls=True)


@pytest.mark.asyncio
async def test_run_query_success_without_rls():
    rls_helper = AsyncMock()

    session = AsyncMock()
    result = MagicMock()
    result.returns_rows = True
    result.keys.return_value = ["n"]
    result.mappings.return_value.all.return_value = [{"n": 1}]
    session.execute = AsyncMock(return_value=result)

    sessionmaker = _session_stack(session)

    with patch(
        "shared_server_libs.agent_db_access.repositories.base_database_repository.ProjectSessionRegistry.get_sessionmaker",
        new=AsyncMock(return_value=sessionmaker),
    ):
        repo = BaseDatabaseRepository(rls_helper)
        out = await repo.run_query("proj", "u@e.com", "SELECT 1 AS n", use_rls=False)

    assert out.success is True
    assert out.row_count == 1
    assert out.rows == [{"n": 1}]
    rls_helper.get_scoped_cell_iids.assert_not_called()
