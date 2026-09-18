from abc import ABC, abstractmethod
from pathlib import Path


class ISkillDiscovery(ABC):
    @abstractmethod
    def discover_skill_files(self, root: Path) -> list[Path]:
        ...

    @abstractmethod
    def read_text(self, path: Path) -> str:
        ...


class FilesystemSkillDiscoveryAdapter(ISkillDiscovery):
    def discover_skill_files(self, root: Path) -> list[Path]:
        return sorted(root.rglob("SKILL.md"))

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")
