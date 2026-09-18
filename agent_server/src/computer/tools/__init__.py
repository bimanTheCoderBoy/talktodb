from typing import Sequence

from langchain_core.tools import BaseTool

from computer.tools.activate_skill import activate_skill
from computer.tools.filesystem import get_fs_tools_for_user


async def get_computer_tools_for_user(user_id: str) -> Sequence[BaseTool]:
    fs_tools = await get_fs_tools_for_user(user_id)
    return [*fs_tools, activate_skill]
