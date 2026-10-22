from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.precheck_outcome import PrecheckOutcome


@dataclass(frozen=True, kw_only=True, slots=True)
class PrecheckResult:
    outcome: PrecheckOutcome
    reason: str | None = None
