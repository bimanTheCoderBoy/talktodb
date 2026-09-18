from langchain_core.tools import tool
from pydantic import BaseModel, Field

from computer.config.logger import get_computer_logger
from computer.skills.skill_registry import SkillRegistry

logger = get_computer_logger(__name__)


class ActivateSkillArgs(BaseModel):
    skill_name: str = Field(
        description="The `name` from available_skills (YAML frontmatter), e.g. canvas_write.",
    )


@tool("activate_skill", args_schema=ActivateSkillArgs, parse_docstring=False)
def activate_skill(skill_name: str) -> str:
    """
    Load full instructions for a skill listed in available_skills.

    Call this before following a skill workflow when the user's task matches a listed skill.
    Returns structured skill content including the SKILL.md body and resource file paths.
    Do not use for skills not listed in available_skills.
    """
    logger.info("[SKILLS] activate_skill called for %r", skill_name)
    try:
        content = SkillRegistry.get().get_skill_content(skill_name)
        logger.info("[SKILLS] activate_skill succeeded for %r", skill_name)
        return content
    except RuntimeError:
        logger.error("[SKILLS] activate_skill failed for %r", skill_name, exc_info=True)
        raise
