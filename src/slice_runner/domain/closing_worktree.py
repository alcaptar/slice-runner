from __future__ import annotations

from enum import StrEnum


class ClosingWorktree(StrEnum):
    RETIRE = "retire"
    KEEP_FOR_RESUMING = "keep-for-resuming"
    NOT_OURS = "not-ours"
    UNEXPECTED = "unexpected"
