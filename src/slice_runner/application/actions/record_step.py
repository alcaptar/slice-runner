from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.event import Event
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.rounds import Rounds

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.closure import Closure
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.feature_slice import FeatureSlice
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.step import Step
    from slice_runner.domain.transition import Transition


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStepParams:
    repo: str
    issue: int
    slice_id: str
    current: Run
    label: IssueLabel | None
    transition: Transition
    spend: HarnessSpend
    feature_slice: FeatureSlice
    pull_request: int | None
    comparison: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStepResult:
    run: Run
    label: IssueLabel | None


class RecordStep:
    def __init__(
        self, *, repository: RunRepository, events: EventLog, clock: Clock, budgets: Budgets, pid: int
    ) -> None:
        self._repository = repository
        self._events = events
        self._clock = clock
        self._budgets = budgets
        self._pid = pid
        self._last_written: dict[tuple[str, int, str], tuple[Step | None, Closure]] = {}

    def execute(self, params: RecordStepParams) -> RecordStepResult:
        run = replace(params.transition.run, spend=params.spend)
        if run != params.current:
            self._repository.write_run(repo=params.repo, issue=params.issue, run=run)
        label = self._labelled(params, step_of=run)
        if not self._repeats_the_last_wait(params, run=run):
            self._emit(params, run=run)

        return RecordStepResult(run=run, label=label)

    def _labelled(self, params: RecordStepParams, *, step_of: Run) -> IssueLabel | None:
        label = IssueLabel.of(closure=params.transition.closure, step=step_of.step)
        if label is params.label:
            return label
        if label is None:
            if params.label is not None:
                self._repository.remove_label(repo=params.repo, issue=params.issue, remove=params.label)

            return None

        self._repository.write_label(repo=params.repo, issue=params.issue, remove=params.label, add=label)

        return label

    def _repeats_the_last_wait(self, params: RecordStepParams, *, run: Run) -> bool:
        key = (params.repo, params.issue, params.slice_id)
        standing = (run.step, params.transition.closure)
        repeats = params.transition.wait_seconds > 0 and self._last_written.get(key) == standing
        self._last_written[key] = standing

        return repeats

    def _emit(self, params: RecordStepParams, *, run: Run) -> None:
        self._events.emit(
            Event(
                slice_id=params.slice_id,
                repo=params.repo,
                issue=params.issue,
                step=run.step,
                at=self._clock.now(),
                spend=params.spend,
                budget_usd=self._budgets.slice_cost_usd,
                rounds=Rounds.of(run, self._budgets),
                closure=params.transition.closure,
                feature_slice=params.feature_slice,
                pull_request=params.pull_request,
                comparison=params.comparison,
                pid=self._pid,
            )
        )
