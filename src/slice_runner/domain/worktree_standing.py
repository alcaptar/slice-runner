from __future__ import annotations

from enum import StrEnum


class WorktreeStanding(StrEnum):
    ABSENT = "absent"
    BRANCH_ONLY = "branch-only"
    MOUNTED = "mounted"
    STALE = "stale"
    TAKEN_ELSEWHERE = "taken-elsewhere"
    FOREIGN_BRANCH = "foreign-branch"
