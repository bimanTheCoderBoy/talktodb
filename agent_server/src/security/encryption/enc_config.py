import os
from pydantic import BaseModel, Field
from typing import Annotated


class EncryptionConfig(BaseModel):
    """Configuration for the encryption pipeline."""
    enabled: Annotated[bool, Field(
        default=os.getenv("ENCRYPTION_ENABLED", "false").lower() == "true"
    )]
    dict_refresh_seconds: Annotated[int, Field(
        default=int(os.getenv("ENC_DICT_REFRESH_SECONDS", "1800"))
    )]
