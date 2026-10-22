from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class ListedWorktree:
    path: str
    branch: str
    prunable: bool
    main: bool
