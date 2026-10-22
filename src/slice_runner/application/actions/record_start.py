from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.closure import Closure
from slice_runner.domain.event import Event
from slice_runner.domain.rounds import Rounds

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.feature_slice import FeatureSlice
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStartParams:
    repo: str
    issue: int
    slice_id: str
    run: Run
    spend: HarnessSpend
    feature_slice: FeatureSlice


class RecordStart:
    def __init__(self, *, events: EventLog, clock: Clock, budgets: Budgets, pid: int) -> None:
        self._events = events
        self._clock = clock
        self._budgets = budgets
        self._pid = pid

    def execute(self, params: RecordStartParams) -> None:
        if params.run.step.is_after_delivery():
            return

        self._events.emit(
            Event(
                slice_id=params.slice_id,
                repo=params.repo,
                issue=params.issue,
                step=params.run.step,
                at=self._clock.now(),
                spend=params.spend,
                budget_usd=self._budgets.slice_cost_usd,
                rounds=Rounds.of(params.run, self._budgets),
                closure=Closure.open(),
                feature_slice=params.feature_slice,
                pid=self._pid,
            )
        )
