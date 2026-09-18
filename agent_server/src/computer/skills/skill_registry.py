from computer.config.logger import get_computer_logger

logger = get_computer_logger(__name__)


class SkillRegistry:
    _available_skills_xml: str | None = None
    _skill_content_by_name: dict[str, str] | None = None

    @classmethod
    def set(cls, available_skills_xml: str, skill_content_by_name: dict[str, str]) -> None:
        cls._available_skills_xml = available_skills_xml
        cls._skill_content_by_name = dict(skill_content_by_name)
        logger.info(
            "[SKILLS] SkillRegistry populated with %d skill(s): %s",
            len(skill_content_by_name),
            sorted(skill_content_by_name.keys()),
        )

    @classmethod
    def get(cls) -> "SkillRegistry":
        if cls._available_skills_xml is None or cls._skill_content_by_name is None:
            msg = "SkillRegistry is not initialized. Call SkillDiscoveryService.init() at server startup."
            logger.error("[SKILLS] %s", msg)
            raise RuntimeError(msg)
        return cls()

    @property
    def available_skills_xml(self) -> str:
        if SkillRegistry._available_skills_xml is None:
            msg = "SkillRegistry is not initialized. Call SkillDiscoveryService.init() at server startup."
            logger.error("[SKILLS] %s", msg)
            raise RuntimeError(msg)
        return SkillRegistry._available_skills_xml

    def get_skill_content(self, skill_name: str) -> str:
        if SkillRegistry._skill_content_by_name is None:
            msg = "SkillRegistry is not initialized. Call SkillDiscoveryService.init() at server startup."
            logger.error("[SKILLS] %s", msg)
            raise RuntimeError(msg)
        if skill_name not in SkillRegistry._skill_content_by_name:
            msg = f"Unknown skill: {skill_name!r}"
            logger.error("[SKILLS] %s (known: %s)", msg, sorted(SkillRegistry._skill_content_by_name.keys()))
            raise RuntimeError(msg)
        logger.info("[SKILLS] Returning skill_content for %r", skill_name)
        return SkillRegistry._skill_content_by_name[skill_name]
