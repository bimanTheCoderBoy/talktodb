from __future__ import annotations

import os
from typing import Annotated

from pydantic import BaseModel, Field


TALKTODB_DB_NAME = "talktodb"


class PostgresConnectionSettings(BaseModel):
    host: Annotated[str, Field(default="localhost")]
    port: Annotated[int, Field(default=5432)]
    user: Annotated[str, Field(default="csv_user")]
    password: Annotated[str, Field(default="csv_password")]
    pool_size: Annotated[int, Field(default=5)]
    max_overflow: Annotated[int, Field(default=10)]

    def get_database_url(self, db_name: str | None = None) -> str:
        key = (db_name or TALKTODB_DB_NAME).lower().strip()
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{key}"
        )

    @classmethod
    def from_env(cls) -> PostgresConnectionSettings:
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", "csv_user"),
            password=os.getenv("DB_PASSWORD", "csv_password"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")),
        )
