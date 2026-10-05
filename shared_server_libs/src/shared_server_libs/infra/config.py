from __future__ import annotations

import os
from typing import Annotated

from pydantic import BaseModel, Field

RANORA_CONFIG_DB_NAME = os.getenv("RANORA_CONFIG_DB_NAME", "ranora_config")


class PostgresConnectionSettings(BaseModel):
    host: Annotated[str, Field(default="localhost")]
    port: Annotated[int, Field(default=5432)]
    user: Annotated[str, Field(default="csv_user")]
    password: Annotated[str, Field(default="csv_password")]
    pool_size: Annotated[int, Field(default=5)]
    max_overflow: Annotated[int, Field(default=10)]

    def get_database_url(self, db_name: str) -> str:
        key = db_name.lower().strip()
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{key}"
        )

    @classmethod
    def from_env(cls) -> PostgresConnectionSettings:
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", os.getenv("API_DB_USER", "csv_user")),
            password=os.getenv("DB_PASSWORD", os.getenv("API_DB_PASSWORD", "csv_password")),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")),
        )


class RedisSettings(BaseModel):
    url: Annotated[str, Field(default="redis://localhost:6379/0")]
    default_ttl_seconds: Annotated[int | None, Field(default=900)]
    key_prefix: Annotated[str, Field(default="rls:cell_iids")]

    @classmethod
    def from_env(cls) -> RedisSettings:
        return cls(
            url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            default_ttl_seconds=int(os.getenv("REDIS_SCOPE_TTL_SECONDS", "900"))
            if os.getenv("REDIS_SCOPE_TTL_SECONDS")
            else 900,
            key_prefix=os.getenv("REDIS_SCOPE_KEY_PREFIX", "rls:cell_iids"),
        )
