import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from deepagents.backends import FilesystemBackend, CompositeBackend
from deepagents.middleware.filesystem import (
    FilesystemMiddleware,
    FilesystemPermission,
)
from langchain_core.tools import BaseTool
from computer.config.tool import get_file_system_tool_config



BASE_DIR = Path(get_file_system_tool_config().base_dir) / "computer"

USERS_DIR = BASE_DIR / "users"
SKILLS_DIR = BASE_DIR / "skills"

USERS_DIR.mkdir(parents=True, exist_ok=True)
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

USER_TOOL_CACHE: dict[str,Sequence[BaseTool]] = {}

# Global/shared backend for skills
SKILL_BACKEND = FilesystemBackend(
    root_dir=str(SKILLS_DIR),
    virtual_mode=True,
)


def get_user_backend(user_id: str) -> FilesystemBackend:
    user_root = USERS_DIR / user_id
    user_root.mkdir(parents=True, exist_ok=True)

    return FilesystemBackend(
        root_dir=str(user_root),
        virtual_mode=True,
    )


async def build_filesystem(user_id: str):
    user_backend = await asyncio.to_thread(get_user_backend, user_id)

    composite_backend = CompositeBackend(
        default=user_backend,
        routes={
            "/skills/": SKILL_BACKEND,
        },
    )

    middleware = FilesystemMiddleware(
        backend=composite_backend,
        # tools=["ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"],
        tools=["ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep"],
        _permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/skills/**"],
                mode="deny",
            ),
            FilesystemPermission(
                operations=["read"],
                paths=["/skills/**"],
                mode="allow",
            ),
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/**"],
                mode="allow",
            ),
        ],
    )

    return middleware


async def get_fs_tools_for_user(user_id: str):
    if user_id not in USER_TOOL_CACHE:
        middleware = await build_filesystem(user_id)
        USER_TOOL_CACHE[user_id] = middleware.tools
    return USER_TOOL_CACHE[user_id]