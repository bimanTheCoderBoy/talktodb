from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from computer.config.logger import get_computer_logger
from computer.skills.skill_discovery_adapter import ISkillDiscovery
from computer.skills.skill_registry import SkillRegistry

logger = get_computer_logger(__name__)


def _extract_frontmatter(text: str) -> tuple[str, str]:
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    rest = stripped[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    elif rest.startswith("\r\n"):
        rest = rest[2:]
    else:
        raise ValueError("Invalid frontmatter opening delimiter")
    end = rest.find("\n---")
    if end == -1:
        raise ValueError("Missing closing --- for frontmatter")
    yaml_block = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return yaml_block, body


def _virtual_skill_dir(skills_root: Path, skill_md_path: Path) -> str:
    skill_root = skill_md_path.parent
    rel = skill_root.relative_to(skills_root).as_posix()
    if rel == ".":
        return "/skills/"
    return f"/skills/{rel}/"


def _build_available_skills_xml(skills: list[tuple[str, str]]) -> str:
    lines = ["<available_skills>"]
    for name, description in skills:
        lines.append(f'  <agent_skill name="{escape(name)}">')
        lines.append(f"    {escape(description)}")
        lines.append("  </agent_skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _heading_to_tag(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip().lower()).strip("_")
    if not slug:
        slug = "section"
    if slug[0].isdigit():
        slug = f"h_{slug}"
    return slug


def _body_to_nested_heading_xml(body: str) -> str:
    """Wrap SKILL.md body in nested XML tags by markdown heading level (# .. ######)."""
    lines = body.splitlines()
    stack: list[tuple[int, str]] = []
    chunks: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = "\n".join(paragraph).strip()
        paragraph.clear()
        if text:
            chunks.append(escape(text))

    def close_through_level(level: int) -> None:
        while stack and stack[-1][0] >= level:
            _, tag = stack.pop()
            chunks.append(f"</{tag}>")

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            flush_paragraph()
            level = len(match.group(1))
            title = match.group(2).strip()
            tag = _heading_to_tag(title)
            close_through_level(level)
            chunks.append(f'<{tag}>')
            stack.append((level, tag))
        else:
            paragraph.append(line)

    flush_paragraph()
    close_through_level(0)

    structured = "\n".join(chunks)
    if structured.strip():
        return structured
    return escape(body.strip())


def _build_skill_content_xml(name: str, body: str, virtual_dir: str) -> str:
    structured_body = _body_to_nested_heading_xml(body)
    footer = (
        f"\n\nSkill directory: {virtual_dir}\n\n"
        "Relative paths in this skill are relative to the skill directory."
    )
    return f'<skill_content name="{escape(name)}">\n{structured_body}{footer}\n</skill_content>'


class SkillDiscoveryService:
    def __init__(self, adapter: ISkillDiscovery, skills_root: Path):
        self._adapter = adapter
        self._skills_root = skills_root

    def init(self) -> None:
        root = self._skills_root
        logger.info("[SKILLS] Starting skill discovery under %s", root)

        if not root.is_dir():
            msg = f"Skills root does not exist: {root}"
            logger.error("[SKILLS] %s", msg)
            raise RuntimeError(msg)

        skill_files = self._adapter.discover_skill_files(root)
        if not skill_files:
            msg = f"No SKILL.md files found under {root}"
            logger.warning("[SKILLS] %s", msg)
            # raise RuntimeError(msg)

        logger.info("[SKILLS] Found %d SKILL.md file(s)", len(skill_files))

        meta_for_prompt: list[tuple[str, str]] = []
        skill_content_by_name: dict[str, str] = {}

        for skill_md_path in skill_files:
            try:
                text = self._adapter.read_text(skill_md_path)
                yaml_block, body = _extract_frontmatter(text)
                data = yaml.safe_load(yaml_block)
            except Exception as e:
                msg = f"Failed to parse {skill_md_path}: {e}"
                logger.error("[SKILLS] %s", msg, exc_info=True)
                raise RuntimeError(msg) from e

            if not isinstance(data, dict):
                msg = f"Invalid frontmatter in {skill_md_path}: expected mapping"
                logger.error("[SKILLS] %s", msg)
                raise RuntimeError(msg)

            name = data.get("name")
            description = data.get("description")
            if not name or not isinstance(name, str):
                msg = f"Missing or invalid 'name' in {skill_md_path}"
                logger.error("[SKILLS] %s", msg)
                raise RuntimeError(msg)
            if description is None or not isinstance(description, str):
                msg = f"Missing or invalid 'description' in {skill_md_path}"
                logger.error("[SKILLS] %s", msg)
                raise RuntimeError(msg)

            if name in skill_content_by_name:
                msg = f"Duplicate skill name {name!r} (file: {skill_md_path})"
                logger.error("[SKILLS] %s", msg)
                raise RuntimeError(msg)

            virtual_dir = _virtual_skill_dir(root, skill_md_path)
            content_xml = _build_skill_content_xml(name, body, virtual_dir)

            meta_for_prompt.append((name, description.strip()))
            skill_content_by_name[name] = content_xml
            logger.info(
                "[SKILLS] Loaded skill name=%r path=%s virtual_dir=%s",
                name,
                skill_md_path,
                virtual_dir,
            )

        available_skills_xml = _build_available_skills_xml(meta_for_prompt)
        SkillRegistry.set(available_skills_xml, skill_content_by_name)

        logger.info("[SKILLS] Discovery succeeded; %d skill(s) registered", len(skill_content_by_name))
        logger.info("[SKILLS] available_skills_xml:\n%s", available_skills_xml)
        for skill_name, content in skill_content_by_name.items():
            logger.info("[SKILLS] skill_content[%r]", skill_name)
