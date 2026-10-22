from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.run_controls import RunControls, RunControlsParams
from slice_runner.domain.activity_log import ActivityLog
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.local_activity_log import LocalActivityLog
from slice_runner.tests.activity_file import ActivityFile
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.control_command_mother import ControlCommandMother
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.slice_identity import SliceIdentity

_WORKTREE = "/repos/slice-runner"
_LOGS = Path("/tmp/slice-runner/logs")
_REPO = "alcaptar/slice-runner"
_ISSUE = 38
_SLICE_ID: SliceIdentity = SubIssueMother.pending().slice_id


class TestRunControls:
    @pytest.fixture
    def controls_runner(self) -> Mock:
        runner: Mock = create_autospec(ControlRunner, spec_set=True, instance=True)
        runner.run.return_value = ControlOutcomeMother.green()
        return runner

    @pytest.fixture
    def action(self, controls_runner: Mock) -> RunControls:
        activity: Mock = create_autospec(ActivityLog, spec_set=True, instance=True)

        return RunControls(controls=controls_runner, activity=activity)

    @staticmethod
    def _params(*, controls: Controls, round_in_progress: int = 1) -> RunControlsParams:
        return RunControlsParams(
            worktree=_WORKTREE,
            controls=controls,
            logs=_LOGS,
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE_ID,
            round_in_progress=round_in_progress,
        )

    def test_an_exempt_repo_runs_no_command(self, action: RunControls, controls_runner: Mock) -> None:
        result = action.execute(self._params(controls=ParentIssueMother.with_exempt_controls().controls))

        controls_runner.run.assert_not_called()
        assert result.outcome is Outcome.DONE

    def test_every_declared_command_runs_even_after_one_of_them_already_failed(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        action.execute(self._params(controls=ParentIssueMother.with_two_controls().controls))

        assert [call.args[0].name for call in controls_runner.run.call_args_list] == [
            ControlCommandMother.LINT_NAME,
            ControlCommandMother.TESTS_NAME,
        ]

    def test_the_round_directory_names_the_slice_and_the_round_number_it_was_given(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        action.execute(
            self._params(controls=ParentIssueMother.with_sources_and_controls().controls, round_in_progress=2)
        )

        expected = _LOGS / _REPO / str(_ISSUE) / _SLICE_ID.canonical / "round-2"
        assert controls_runner.run.call_args.kwargs["out"] == expected
        assert controls_runner.run.call_args.kwargs["worktree"] == _WORKTREE

    def test_a_red_controls_log_reaches_the_result_so_the_next_implementation_can_read_it(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.return_value = ControlOutcomeMother.red()

        result = action.execute(self._params(controls=ParentIssueMother.with_sources_and_controls().controls))

        assert result.red_logs == (ControlOutcomeMother.LOG,)
        assert result.outcome is Outcome.FAILED

    def test_a_control_that_could_not_be_measured_is_not_read_as_red(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.return_value = ControlOutcomeMother.unknown()

        result = action.execute(self._params(controls=ParentIssueMother.with_sources_and_controls().controls))

        assert result.red_logs == ()
        assert result.outcome is Outcome.INDETERMINATE


class TestTheControlsAnnouncedBeforeTheyRun(WithTheDurableStoresOutOfTheRealHome):
    _COORDINATES = SliceCoordinates(repo=_REPO, issue=_ISSUE, slice_id=CanonicalSliceId.of_text(_SLICE_ID.canonical))

    def _action(self) -> RunControls:
        runner: Mock = create_autospec(ControlRunner, spec_set=True, instance=True)
        runner.run.return_value = ControlOutcomeMother.green()

        return RunControls(controls=runner, activity=LocalActivityLog(clock=self.frozen_at()))

    @staticmethod
    def _params(*, controls: Controls) -> RunControlsParams:
        return RunControlsParams(
            worktree=_WORKTREE,
            controls=controls,
            logs=_LOGS,
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE_ID,
            round_in_progress=1,
        )

    def test_a_round_with_two_controls_leaves_exactly_two_lines_in_the_order_they_run(self, tmp_path: Path) -> None:
        self._action().execute(self._params(controls=ParentIssueMother.with_two_controls().controls))

        assert ActivityFile.what_was_done(tmp_path, self._COORDINATES) == [
            ("controls", ControlCommandMother.LINT_NAME, ControlCommandMother.LINT_COMMAND),
            ("controls", ControlCommandMother.TESTS_NAME, ControlCommandMother.TESTS_COMMAND),
        ]

    def test_a_second_round_leaves_only_the_lines_of_that_round(self, tmp_path: Path) -> None:
        action = self._action()
        action.execute(self._params(controls=ParentIssueMother.with_two_controls().controls))

        action.execute(self._params(controls=ParentIssueMother.with_sources_and_controls().controls))

        assert len(ActivityFile.lines_of(tmp_path, self._COORDINATES)) == 1
