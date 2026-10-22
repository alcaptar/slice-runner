from __future__ import annotations

from enum import StrEnum


class IssueState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
