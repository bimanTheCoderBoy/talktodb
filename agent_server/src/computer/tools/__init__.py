from typing import Sequence

from langchain_core.tools import BaseTool

from computer.tools.activate_skill import activate_skill
from computer.tools.database_context import (
    CATALOG_CONTEXT_TOOLS,
    get_run_db_query_tool,
)
from computer.tools.dynamic import DYNAMIC_TOOLS
from computer.tools.filesystem import get_fs_tools_for_user


async def get_computer_tools_for_user(
    user_id: str,
    *,
    project_name: str | None = None,
) -> Sequence[BaseTool]:
    fs_tools = await get_fs_tools_for_user(user_id)
    tools: list[BaseTool] = [*fs_tools, activate_skill, *CATALOG_CONTEXT_TOOLS, *DYNAMIC_TOOLS]
    if project_name:
        tools.append(get_run_db_query_tool(project_name, user_id))
    return tools
