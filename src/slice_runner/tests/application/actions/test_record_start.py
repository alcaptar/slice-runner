from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.record_start import RecordStart, RecordStartParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.clock import Clock
from slice_runner.domain.closure import Closure
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.rounds import Rounds
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO = "alcaptar/slice-runner"
_ISSUE = 172
_SLICE_ID = "slice-14"
_NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
_PID = 48213


class TestRecordStart:
    @pytest.fixture
    def events(self) -> Mock:
        events: Mock = create_autospec(EventLog, spec_set=True, instance=True)
        return events

    @pytest.fixture
    def clock(self) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = _NOW
        return clock

    @pytest.fixture
    def action(self, events: Mock, clock: Mock) -> RecordStart:
        return RecordStart(events=events, clock=clock, budgets=Budgets(), pid=_PID)

    @staticmethod
    def _params(run: Run) -> RecordStartParams:
        return RecordStartParams(
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE_ID,
            run=run,
            spend=HarnessSpendMother.of_the_implementer_call(),
            feature_slice=FeatureSliceMother.of_the_feature(),
        )

    def test_the_start_is_reported_on_the_step_the_run_starts_at_with_the_run_still_open(
        self, action: RecordStart, events: Mock
    ) -> None:
        action.execute(self._params(RunMother.implementing()))

        emitted = events.emit.call_args.args[0]
        assert (emitted.step, emitted.closure) == (Step.IMPLEMENT, Closure.open())

    def test_the_start_carries_the_counters_of_the_run_with_their_limits_and_the_cost_limit(
        self, action: RecordStart, events: Mock
    ) -> None:
        run = RunMother.implementing()

        action.execute(self._params(run))

        emitted = events.emit.call_args.args[0]
        assert emitted.rounds == Rounds.of(run, Budgets())
        assert emitted.budget_usd == Budgets().slice_cost_usd

    def test_the_start_names_the_slice_the_instant_the_spend_paid_so_far_and_the_feature(
        self, action: RecordStart, events: Mock
    ) -> None:
        action.execute(self._params(RunMother.implementing()))

        emitted = events.emit.call_args.args[0]
        assert (emitted.slice_id, emitted.repo, emitted.issue, emitted.at, emitted.spend, emitted.feature_slice) == (
            _SLICE_ID,
            _REPO,
            _ISSUE,
            _NOW,
            HarnessSpendMother.of_the_implementer_call(),
            FeatureSliceMother.of_the_feature(),
        )

    def test_the_start_carries_the_pid_of_the_process_and_no_pull_request_because_none_is_open_yet(
        self, action: RecordStart, events: Mock
    ) -> None:
        action.execute(self._params(RunMother.implementing()))

        emitted = events.emit.call_args.args[0]
        assert (emitted.pid, emitted.pull_request) == (_PID, None)

    @pytest.mark.parametrize(
        ("run", "step"),
        [
            (RunMother.running_the_controls(), Step.RUN_CONTROLS),
            (RunMother.judging(), Step.VERIFY),
            (RunMother.about_to_open_the_pull_request(), Step.OPEN_PULL_REQUEST),
        ],
    )
    def test_a_run_resumed_at_a_step_that_works_reports_that_step(
        self, action: RecordStart, events: Mock, run: Run, step: Step
    ) -> None:
        action.execute(self._params(run))

        assert events.emit.call_args.args[0].step is step

    @pytest.mark.parametrize("run", [RunMother.awaiting_ci(), RunMother.awaiting_merge()])
    def test_a_run_that_only_reads_the_integration_or_the_pull_request_reports_nothing(
        self, action: RecordStart, events: Mock, run: Run
    ) -> None:
        action.execute(self._params(run))

        events.emit.assert_not_called()
