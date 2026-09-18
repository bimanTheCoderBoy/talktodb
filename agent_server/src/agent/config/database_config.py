from pydantic import BaseModel, Field
from typing import Annotated
import os


class DBConfig(BaseModel):
    host: Annotated[str, Field(default=os.getenv("DB_HOST", "localhost"))]
    port: Annotated[int, Field(default=int(os.getenv("DB_PORT", "5432")))]
    user: Annotated[str, Field(default=os.getenv("DB_USER", "csv_user"))]
    password: Annotated[str, Field(default=os.getenv("DB_PASSWORD", "csv_password"))]
    min_size: Annotated[int, Field(default=int(os.getenv("DB_POOL_MIN_SIZE", "1")))]
    max_size: Annotated[int, Field(default=int(os.getenv("DB_POOL_MAX_SIZE", "10")))]

