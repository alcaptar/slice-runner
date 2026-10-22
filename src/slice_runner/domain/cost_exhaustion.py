from __future__ import annotations

from enum import StrEnum


class CostExhaustion(StrEnum):
    WITHIN_BUDGET = "within-budget"
    CALL_UNMEASURED = "call-unmeasured"
    TOTAL_EXCEEDED = "total-exceeded"
