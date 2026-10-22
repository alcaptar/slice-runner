from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class GhRetryDecision:
    retry: bool
    wait_seconds: int = 0
