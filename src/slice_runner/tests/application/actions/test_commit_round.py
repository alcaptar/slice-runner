from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.commit_round import CommitRound, CommitRoundParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.clock import Clock
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.protected_branch import ProtectedBranch
from slice_runner.domain.step import Step
from slice_runner.domain.workspace import Workspace
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother
from slice_runner.tests.mothers.run_mother import RunMother

_WORKTREE = "/repos/slice-runner"
_BRANCH = "slice/14-una-correccion-va-en-su-propio-commit"
_REPO = "alcaptar/slice-runner"
_ISSUE = 172
_SLICE_ID = "slice-14"
_NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
_PID = 48213
_PULL_REQUEST = 151
_MESSAGE = "feat(una-correccion): el commit de la vuelta 2\n\nCo-Authored-By: Claude <noreply@anthropic.com>"


class TestCommitRound:
    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.current_branch.return_value = _BRANCH
        workspace.staged.return_value = ("src/mod.py",)
        return workspace

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
    def action(self, workspace: Mock, events: Mock, clock: Mock) -> CommitRound:
        return CommitRound(workspace=workspace, events=events, clock=clock, budgets=Budgets(), pid=_PID)

    @staticmethod
    def _params() -> CommitRoundParams:
        return CommitRoundParams(
            worktree=_WORKTREE,
            branch=_BRANCH,
            message=_MESSAGE,
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE_ID,
            run=RunMother.implementing(),
            spend=HarnessSpend.nothing(),
            feature_slice=FeatureSliceMother.of_the_feature(),
            pull_request=_PULL_REQUEST,
        )

    def test_a_round_with_nothing_staged_names_the_pull_request_and_the_pid_in_its_event(
        self, action: CommitRound, workspace: Mock, events: Mock
    ) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        emitted = events.emit.call_args.args[0]
        assert (emitted.pull_request, emitted.pid) == (_PULL_REQUEST, _PID)

    def test_a_round_with_something_staged_is_committed_with_the_message_it_was_given(
        self, action: CommitRound, workspace: Mock
    ) -> None:
        action.execute(self._params())

        workspace.commit.assert_called_once_with(worktree=_WORKTREE, message=_MESSAGE)

    def test_a_round_with_nothing_staged_leaves_no_commit(self, action: CommitRound, workspace: Mock) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        workspace.commit.assert_not_called()

    def test_a_round_with_nothing_staged_leaves_a_durable_event_naming_it(
        self, action: CommitRound, workspace: Mock, events: Mock
    ) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        emitted = events.emit.call_args.args[0]
        assert (
            emitted.round_without_changes,
            emitted.step,
            emitted.slice_id,
            emitted.repo,
            emitted.issue,
            emitted.at,
        ) == (
            True,
            Step.RUN_CONTROLS,
            _SLICE_ID,
            _REPO,
            _ISSUE,
            _NOW,
        )

    def test_the_round_without_changes_event_names_the_parent_issue_and_the_slice(
        self, action: CommitRound, workspace: Mock, events: Mock
    ) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        assert events.emit.call_args.args[0].feature_slice == FeatureSliceMother.of_the_feature()

    def test_a_round_that_commits_leaves_no_round_without_changes_event(
        self, action: CommitRound, events: Mock
    ) -> None:
        action.execute(self._params())

        events.emit.assert_not_called()

    @pytest.mark.parametrize("protected", list(ProtectedBranch))
    def test_a_protected_branch_stops_the_round_before_anything_is_committed(
        self, action: CommitRound, workspace: Mock, protected: ProtectedBranch
    ) -> None:
        workspace.current_branch.return_value = str(protected)

        with pytest.raises(ProtectedBranchError, match=str(protected)):
            action.execute(self._params())

        workspace.commit.assert_not_called()

    def test_standing_on_a_branch_that_is_not_the_one_the_slice_declared_stops_the_round(
        self, action: CommitRound, workspace: Mock
    ) -> None:
        workspace.current_branch.return_value = "slice/07-otra-slice"

        with pytest.raises(BranchMismatchError, match="slice/07-otra-slice"):
            action.execute(self._params())

        workspace.commit.assert_not_called()
