from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.gh_retry_decision import GhRetryDecision

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets


@dataclass(frozen=True, kw_only=True, slots=True)
class GhRetryPolicy:
    budgets: Budgets

    def after_a_failure(self, *, transient: bool, safe_to_repeat: bool, attempted: int) -> GhRetryDecision:
        if not transient or not safe_to_repeat or attempted >= self.budgets.gh_retries:
            return GhRetryDecision(retry=False)

        return GhRetryDecision(retry=True, wait_seconds=self.budgets.seconds_between_gh_retries)
