from __future__ import annotations

from enum import StrEnum


class PullRequestMergeability(StrEnum):
    MERGEABLE = "mergeable"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"
