from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.reset_slice import ResetSlice, ResetSliceParams
from slice_runner.domain.clock import Clock
from slice_runner.domain.exceptions import NoRecognizableSpecError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_repository import RunRepository
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_REPO = "alcaptar/slice-runner"
_AT = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)


class _Recorder:
    def __init__(self) -> None:
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        self.clock.now.return_value = _AT

    @property
    def action(self) -> ResetSlice:
        return ResetSlice(repository=self.repository, clock=self.clock)


class TestResettingASlice:
    def test_the_persisted_execution_state_is_cleared(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.clear_run.assert_called_once_with(repo=_REPO, issue=subissue.number)

    def test_the_label_left_on_the_subissue_is_pending(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.write_label.assert_called_once_with(
            repo=_REPO, issue=subissue.number, remove=IssueLabel.BLOCKED_CONTROLS, add=IssueLabel.PENDING
        )

    def test_a_comment_declares_the_reset_and_names_the_moment_it_happened(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.mark_reset.assert_called_once_with(
            repo=_REPO, issue=subissue.number, branch=subissue.branch, at=_AT
        )

    def test_the_result_carries_the_subissue_with_no_run_and_the_pending_label(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        result = recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        assert result.subissue.run is None
        assert result.subissue.label is IssueLabel.PENDING

    def test_the_intention_the_criteria_and_the_signal_are_never_written_and_come_back_unchanged(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        result = recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        assert result.subissue.intention == subissue.intention
        assert result.subissue.criteria == subissue.criteria
        assert result.subissue.signal == subissue.signal

    def test_a_subissue_carrying_neither_intention_nor_criteria_is_rejected_before_writing_anything(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.without_a_recognizable_spec()

        with pytest.raises(NoRecognizableSpecError, match=str(subissue.number)):
            recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.clear_run.assert_not_called()
        recorder.repository.write_label.assert_not_called()
        recorder.repository.mark_reset.assert_not_called()

    def test_a_slice_that_never_ran_is_reset_with_no_error_and_the_same_operations_as_one_that_did(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.pending()

        result = recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.clear_run.assert_called_once_with(repo=_REPO, issue=subissue.number)
        recorder.repository.mark_reset.assert_called_once_with(
            repo=_REPO, issue=subissue.number, branch=subissue.branch, at=_AT
        )
        assert result.subissue.run is None
        assert result.subissue.label is IssueLabel.PENDING

    def test_a_slice_already_labelled_pending_gets_no_redundant_label_edit(self) -> None:
        recorder = _Recorder()
        subissue = SubIssueMother.pending()

        recorder.action.execute(ResetSliceParams(repo=_REPO, subissue=subissue))

        recorder.repository.write_label.assert_not_called()
