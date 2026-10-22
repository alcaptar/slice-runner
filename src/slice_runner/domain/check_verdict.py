from __future__ import annotations

from enum import StrEnum


class CheckVerdict(StrEnum):
    READY = "ready"
    WARNING = "warning"
    MISSING = "missing"
    UNKNOWN = "unknown"
