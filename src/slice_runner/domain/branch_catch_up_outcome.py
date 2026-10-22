from __future__ import annotations

from enum import StrEnum


class BranchCatchUpOutcome(StrEnum):
    CAUGHT_UP = "caught-up"
    CONFLICTING = "conflicting"
