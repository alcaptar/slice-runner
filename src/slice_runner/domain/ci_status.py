from __future__ import annotations

from enum import StrEnum


class CiStatus(StrEnum):
    GREEN = "green"
    RED = "red"
    PENDING = "pending"
    NO_CHECKS = "no-checks"
    UNKNOWN = "unknown"
