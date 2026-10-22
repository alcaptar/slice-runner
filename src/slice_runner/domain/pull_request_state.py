from __future__ import annotations

from enum import StrEnum


class PullRequestState(StrEnum):
    MERGED = "merged"
    OPEN = "open"
    CLOSED = "closed"
