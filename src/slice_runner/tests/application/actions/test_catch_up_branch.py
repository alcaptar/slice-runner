from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.catch_up_branch import CatchUpBranch, CatchUpBranchParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.outcome import Outcome
from slice_runner.tests.mothers.branch_catch_up_mother import BranchCatchUpMother

_WORKTREE = "/repos/slice-runner"
_BRANCH = "slice/03-catch-up"
_BASE = "master"


class TestCatchUpBranch:
    @pytest.fixture
    def branches(self) -> Mock:
        doubled: Mock = create_autospec(Branches, spec_set=True, instance=True)
        doubled.catch_up.return_value = BranchCatchUpMother.caught_up()
        return doubled

    @pytest.fixture
    def action(self, branches: Mock) -> CatchUpBranch:
        return CatchUpBranch(branches=branches)

    @staticmethod
    def _params() -> CatchUpBranchParams:
        return CatchUpBranchParams(worktree=_WORKTREE, branch=_BRANCH, base=_BASE)

    def test_it_asks_the_port_to_catch_up_the_declared_branch_against_its_base(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        action.execute(self._params())

        branches.catch_up.assert_called_once_with(worktree=_WORKTREE, name=_BRANCH, base=_BASE)

    def test_a_branch_caught_up_projects_to_done(self, action: CatchUpBranch, branches: Mock) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.caught_up()

        result = action.execute(self._params())

        assert result.outcome is Outcome.DONE

    def test_a_conflicting_catch_up_projects_to_conflicting(self, action: CatchUpBranch, branches: Mock) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        result = action.execute(self._params())

        assert result.outcome is Outcome.CONFLICTING

    def test_a_branch_caught_up_carries_no_conflicting_paths(self, action: CatchUpBranch, branches: Mock) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.caught_up()

        result = action.execute(self._params())

        assert result.conflicting_paths == ()

    def test_a_conflicting_catch_up_carries_the_paths_git_reported(self, action: CatchUpBranch, branches: Mock) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        result = action.execute(self._params())

        assert result.conflicting_paths == BranchCatchUpMother.CONFLICTING_PATHS
