from __future__ import annotations

from unittest.mock import Mock, call, create_autospec

import pytest

from slice_runner.application.actions.deliver_slice import DeliverSlice, DeliverSliceParams
from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.forum import Forum
from slice_runner.domain.protected_branch import ProtectedBranch
from slice_runner.domain.workspace import Workspace

_WORKTREE = "/repos/slice-runner"
_REPO = "alcaptar/slice-runner"
_BRANCH = "slice/08-entrega-de-la-slice"
_BASE = "master"
_TITLE = "feat(entrega-de-la-slice): commitear solo lo juzgado y abrir la pull request"
_BODY = "## Intencion\nsin esto el programa verifica y no entrega\n\nCloses #46\n"


class TestDeliverSlice:
    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.current_branch.return_value = _BRANCH
        return workspace

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_request.return_value = None
        forum.create_pull_request.return_value = 48
        return forum

    @pytest.fixture
    def action(self, workspace: Mock, forum: Mock) -> DeliverSlice:
        return DeliverSlice(workspace=workspace, forum=forum)

    @staticmethod
    def _params() -> DeliverSliceParams:
        return DeliverSliceParams(worktree=_WORKTREE, repo=_REPO, branch=_BRANCH, base=_BASE, title=_TITLE, body=_BODY)

    def test_the_branch_is_pushed_only_after_checking_which_branch_it_stands_on(
        self, action: DeliverSlice, workspace: Mock
    ) -> None:
        action.execute(self._params())

        assert workspace.mock_calls == [
            call.current_branch(worktree=_WORKTREE),
            call.push(worktree=_WORKTREE, branch=_BRANCH),
        ]

    def test_the_number_of_the_pull_request_it_opened_comes_back(self, action: DeliverSlice, forum: Mock) -> None:
        assert action.execute(self._params()) == 48

        forum.create_pull_request.assert_called_once_with(
            repo=_REPO, branch=_BRANCH, base=_BASE, title=_TITLE, body=_BODY
        )

    def test_a_branch_that_already_has_an_open_pull_request_lands_the_new_commit_without_opening_a_second_one(
        self, action: DeliverSlice, workspace: Mock, forum: Mock
    ) -> None:
        forum.open_pull_request.return_value = 48

        assert action.execute(self._params()) == 48

        workspace.push.assert_called_once_with(worktree=_WORKTREE, branch=_BRANCH)
        forum.create_pull_request.assert_not_called()

    def test_only_an_open_pull_request_is_asked_about_so_a_closed_one_does_not_block_the_next_delivery(
        self, action: DeliverSlice, forum: Mock
    ) -> None:
        action.execute(self._params())

        forum.open_pull_request.assert_called_once_with(repo=_REPO, branch=_BRANCH)
        forum.any_pull_request.assert_not_called()

    @pytest.mark.parametrize("protected", list(ProtectedBranch))
    def test_a_protected_branch_stops_the_delivery_before_anything_is_pushed(
        self, action: DeliverSlice, workspace: Mock, forum: Mock, protected: ProtectedBranch
    ) -> None:
        workspace.current_branch.return_value = str(protected)

        with pytest.raises(ProtectedBranchError, match=str(protected)):
            action.execute(self._params())

        workspace.push.assert_not_called()
        forum.create_pull_request.assert_not_called()

    def test_standing_on_a_branch_that_is_not_the_one_the_slice_declared_stops_the_delivery(
        self, action: DeliverSlice, workspace: Mock, forum: Mock
    ) -> None:
        workspace.current_branch.return_value = "slice/07-otra-slice"

        with pytest.raises(BranchMismatchError, match="slice/07-otra-slice"):
            action.execute(self._params())

        workspace.push.assert_not_called()
        forum.create_pull_request.assert_not_called()
