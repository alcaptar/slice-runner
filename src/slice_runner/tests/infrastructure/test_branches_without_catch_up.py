from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.branches import Branches
from slice_runner.infrastructure.branches_without_catch_up import BranchesWithoutCatchUp

_WORKTREE = "/repos/slice-runner"
_BRANCH = "slice/01-la-rama-se-pone-al-dia-antes-de-implementar"
_BASE = "master"


class TestBranchesWithoutCatchUp:
    @pytest.fixture
    def real(self) -> Mock:
        doubled: Mock = create_autospec(Branches, spec_set=True, instance=True)
        return doubled

    @pytest.fixture
    def branches(self, real: Mock) -> BranchesWithoutCatchUp:
        return BranchesWithoutCatchUp(branches=real)

    def test_putting_a_branch_up_to_date_answers_that_there_was_nothing_to_merge(
        self, branches: BranchesWithoutCatchUp
    ) -> None:
        caught_up = branches.catch_up(worktree=_WORKTREE, name=_BRANCH, base=_BASE)

        assert caught_up.outcome is BranchCatchUpOutcome.CAUGHT_UP

    def test_putting_a_branch_up_to_date_never_reaches_the_port_so_no_merge_can_be_launched(
        self, branches: BranchesWithoutCatchUp, real: Mock
    ) -> None:
        branches.catch_up(worktree=_WORKTREE, name=_BRANCH, base=_BASE)

        real.catch_up.assert_not_called()

    def test_how_far_behind_the_base_is_still_asked_of_the_port(
        self, branches: BranchesWithoutCatchUp, real: Mock
    ) -> None:
        branches.commits_behind_remote(worktree=_WORKTREE, base=_BASE)

        real.commits_behind_remote.assert_called_once_with(worktree=_WORKTREE, base=_BASE)
