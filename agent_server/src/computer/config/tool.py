import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from typing import Annotated


def _resolve_data_dir() -> str:
    raw = os.getenv("TALKTODB_DATA_DIR", "./talktodb_data")
    return str(Path(raw).expanduser().resolve(strict=False))


class FileSystemToolConfig(BaseModel):
    """Root for computer agent skills and per-user filesystem tools."""

    base_dir: Annotated[str, Field(default_factory=_resolve_data_dir)]


@lru_cache(maxsize=1)
def get_file_system_tool_config() -> FileSystemToolConfig:
    return FileSystemToolConfig()
