from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.worktree_standing import WorktreeStanding


@dataclass(frozen=True, kw_only=True, slots=True)
class WorktreeClassification:
    standing: WorktreeStanding
    conflicting_path: str = ""
