from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.infrastructure.claude_config import ClaudeConfig

if TYPE_CHECKING:
    from pathlib import Path


class LocalSkillLibrary(SkillLibrary):
    TREES: ClassVar[tuple[str, ...]] = ("skills", "plugins")

    def root(self) -> Path:
        return ClaudeConfig.root()

    def directories(self) -> tuple[Path, ...]:
        root = ClaudeConfig.root()

        return tuple(tree for tree in (root / name for name in self.TREES) if tree.is_dir())

    def installed(self, name: str) -> Path | None:
        candidate = ClaudeConfig.root() / "skills" / name

        return candidate.resolve() if candidate.is_dir() else None
