from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class SpendOfStepParams:
    repo: str
    issue: int
    slice_id: str
    step: Step


class SpendOfStep:
    def __init__(self, *, trace: CallTrace, spend_log: CallSpendLog) -> None:
        self._trace = trace
        self._spend_log = spend_log

    def execute(self, params: SpendOfStepParams) -> HarnessSpend:
        sessions = self._trace.sessions_of(
            repo=params.repo, issue=params.issue, slice_id=params.slice_id, step=params.step
        )

        return self._spend_log.spend_of(sessions)
