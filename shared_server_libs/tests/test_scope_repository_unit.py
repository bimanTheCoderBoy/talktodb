from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import (
    UserProjectScopeRepository,
)


@pytest.mark.asyncio
async def test_get_cell_iids_returns_list_when_row_present():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = ["cell-a", "cell-b"]
    session.execute = AsyncMock(return_value=result_mock)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    sessionmaker = MagicMock(return_value=session_cm)

    with patch(
        "shared_server_libs.agent_db_access.repositories.user_project_scope_repository.UserSessionRegistry.get_sessionmaker",
        new=AsyncMock(return_value=sessionmaker),
    ):
        repo = UserProjectScopeRepository()
        iids = await repo.get_cell_iids("MyProject", "User@Example.com")

    assert iids == ["cell-a", "cell-b"]
    session.execute.assert_awaited_once()
    call_params = session.execute.await_args[0][1]
    assert call_params["email"] == "user@example.com"
    assert call_params["project"] == "myproject"


@pytest.mark.asyncio
async def test_get_cell_iids_returns_empty_when_no_row():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    sessionmaker = MagicMock(return_value=session_cm)

    with patch(
        "shared_server_libs.agent_db_access.repositories.user_project_scope_repository.UserSessionRegistry.get_sessionmaker",
        new=AsyncMock(return_value=sessionmaker),
    ):
        repo = UserProjectScopeRepository()
        iids = await repo.get_cell_iids("proj", "a@b.c")

    assert iids == []
