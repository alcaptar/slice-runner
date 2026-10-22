from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.rescue_staged_work import RescueStagedWork, RescueStagedWorkParams
from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.protected_branch import ProtectedBranch
from slice_runner.domain.workspace import Workspace

_WORKTREE = "/repos/slice-runner"
_BRANCH = "slice/14-una-correccion-va-en-su-propio-commit"
_MESSAGE = "feat(una-correccion): rescate\n\nCo-Authored-By: Claude <noreply@anthropic.com>"


class TestRescueStagedWork:
    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.current_branch.return_value = _BRANCH
        workspace.staged.return_value = ("src/mod.py",)
        return workspace

    @pytest.fixture
    def action(self, workspace: Mock) -> RescueStagedWork:
        return RescueStagedWork(workspace=workspace)

    @staticmethod
    def _params() -> RescueStagedWorkParams:
        return RescueStagedWorkParams(worktree=_WORKTREE, branch=_BRANCH, message=_MESSAGE)

    def test_work_left_staged_is_committed_with_the_message_it_was_given(
        self, action: RescueStagedWork, workspace: Mock
    ) -> None:
        action.execute(self._params())

        workspace.commit.assert_called_once_with(worktree=_WORKTREE, message=_MESSAGE)

    def test_a_clean_index_leaves_no_commit(self, action: RescueStagedWork, workspace: Mock) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        workspace.commit.assert_not_called()

    @pytest.mark.parametrize("protected", list(ProtectedBranch))
    def test_a_protected_branch_stops_the_rescue_before_anything_is_committed(
        self, action: RescueStagedWork, workspace: Mock, protected: ProtectedBranch
    ) -> None:
        workspace.current_branch.return_value = str(protected)

        with pytest.raises(ProtectedBranchError):
            action.execute(self._params())

        workspace.commit.assert_not_called()

    def test_standing_on_another_branch_stops_the_rescue(self, action: RescueStagedWork, workspace: Mock) -> None:
        workspace.current_branch.return_value = "slice/07-otra-slice"

        with pytest.raises(BranchMismatchError):
            action.execute(self._params())

        workspace.commit.assert_not_called()
