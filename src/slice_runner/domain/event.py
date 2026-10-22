from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.closure import Closure
    from slice_runner.domain.feature_slice import FeatureSlice
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.rounds import Rounds
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Event:
    slice_id: str
    repo: str
    issue: int
    step: Step | None
    at: datetime
    spend: HarnessSpend
    budget_usd: float
    rounds: Rounds
    closure: Closure
    feature_slice: FeatureSlice | None
    round_without_changes: bool = False
    pull_request: int | None = None
    pid: int | None = None
    comparison: str | None = None

    @property
    def slice_key(self) -> tuple[str, int, str]:
        return self.repo, self.issue, self.slice_id
