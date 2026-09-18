from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared_server_libs.agent_db_access.repositories.rls_adapter_helper import RLSAdapterHelper
from shared_server_libs.db_infra.config import RedisSettings


@pytest.mark.asyncio
async def test_get_scoped_cell_iids_cache_miss_then_hit():
    scope_repo = AsyncMock()
    scope_repo.get_cell_iids = AsyncMock(return_value=["c1", "c2"])

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=[None, '["c1", "c2"]'])
    redis.set = AsyncMock()

    settings = RedisSettings(url="redis://localhost/0", default_ttl_seconds=60, key_prefix="rls:cell_iids")
    helper = RLSAdapterHelper(scope_repo, redis, settings)

    first = await helper.get_scoped_cell_iids("Proj", "a@b.com")
    second = await helper.get_scoped_cell_iids("Proj", "a@b.com")

    assert first == ["c1", "c2"]
    assert second == ["c1", "c2"]
    scope_repo.get_cell_iids.assert_awaited_once_with("Proj", "a@b.com")
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_deletes_key():
    scope_repo = AsyncMock()
    redis = AsyncMock()
    redis.delete = AsyncMock()

    settings = RedisSettings(key_prefix="rls:cell_iids")
    helper = RLSAdapterHelper(scope_repo, redis, settings)

    await helper.invalidate("MyProj", "User@Test.com")
    redis.delete.assert_awaited_once_with("rls:cell_iids:myproj:user@test.com")
