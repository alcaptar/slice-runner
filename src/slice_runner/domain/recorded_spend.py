from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordedSpend:
    cost_usd: float
    turns: int
    duration_ms: int
    cache_read_tokens: int
    input_tokens: int
    output_tokens: int
