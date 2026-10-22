from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from slice_runner.domain.canonical_slice_id import CanonicalSliceId


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceIdentity:
    ordinal: int
    name: str
    user_story: str | None = None

    WORKTREES_DIRECTORY: ClassVar[str] = ".worktrees"

    @property
    def canonical_id(self) -> CanonicalSliceId:
        return CanonicalSliceId.of_parts(ordinal=self.ordinal, user_story=self.user_story)

    @property
    def canonical(self) -> str:
        return self.canonical_id.text

    @property
    def _suffix_and_name(self) -> str:
        return f"{self.canonical_id.branch_suffix}-{self.name}"

    @property
    def branch(self) -> str:
        return f"slice/{self._suffix_and_name}"

    def worktree_under(self, root: str) -> str:
        return str(PurePosixPath(root) / self.WORKTREES_DIRECTORY / self._suffix_and_name)

    @classmethod
    def worktrees_exclusion(cls) -> str:
        return f"/{cls.WORKTREES_DIRECTORY}/"
