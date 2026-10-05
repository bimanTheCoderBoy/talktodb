from __future__ import annotations

import json
import logging

from redis.asyncio import Redis

from shared_server_libs.infra.config import RedisSettings
from shared_server_libs.agent_db_access.repositories.user_project_scope_repository import UserProjectScopeRepository

logger = logging.getLogger(__name__)

class RLSCacheBase:
    """Base class for cache operations."""

    def __init__(self, redis_client: Redis, redis_settings: RedisSettings) -> None:
        self._redis = redis_client
        self._settings = redis_settings

    def _cache_key(self, project_name: str, email: str) -> str:
        project = project_name.lower().strip()
        normalized_email = email.strip().lower()
        return f"{self._settings.key_prefix}:{project}:{normalized_email}"

class RLSAdapterHelper(RLSCacheBase):
    """Caches scoped cell IIDs from the user DB; supports explicit invalidation."""

    def __init__(
        self,
        scope_repository: UserProjectScopeRepository,
        redis_client: Redis,
        redis_settings: RedisSettings,
    ) -> None:
        super().__init__(redis_client, redis_settings)
        self._scope_repository = scope_repository

    async def get_scoped_cell_iids(self, project_name: str, email: str) -> list[str]:
        key = self._cache_key(project_name, email)
        # cached = await self._redis.get(key)
        cached = None
        if cached is not None:
            try:
                data = json.loads(cached)
                if isinstance(data, list):
                    return [str(x) for x in data]
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in scope cache for key=%s; reloading", key)
                await self._redis.delete(key)

        iids = await self._scope_repository.get_cell_iids(project_name, email)
        payload = json.dumps(iids)
        if self._settings.default_ttl_seconds:
            await self._redis.set(key, payload, ex=self._settings.default_ttl_seconds)
        else:
            await self._redis.set(key, payload)
        return iids

    



class RLSCacheAdapterInvalidator(RLSCacheBase):
    """Invalidates the cache for a given project and email."""

    def __init__(self, redis_client: Redis, redis_settings: RedisSettings) -> None:
        super().__init__(redis_client, redis_settings)

    async def invalidate(self, project_name: str, email: str) -> None:
        key = self._cache_key(project_name, email)
        await self._redis.delete(key)