from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    BLOCKED = "blocked"
    ABORTED = "aborted"
