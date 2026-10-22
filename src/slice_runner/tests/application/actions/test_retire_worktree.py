from __future__ import annotations

from typing import ClassVar
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.retire_worktree import RetireWorktree, RetireWorktreeParams
from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.domain.worktrees import Worktrees
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class _Retiring:
    ROOT: ClassVar[str] = ListedWorktreeMother.ROOT
    BRANCH: ClassVar[str] = SubIssueMother.pending().branch
    PATH: ClassVar[str] = SubIssueMother.pending().slice_id.worktree_under(ROOT)

    def __init__(self) -> None:
        self.worktrees: Mock = create_autospec(Worktrees, spec_set=True, instance=True)
        self.worktrees.is_mounted.return_value = True
        self.worktrees.has_uncommitted_work.return_value = False
        self.worktrees.local_only_commits.return_value = 0

    def retire(self) -> WorktreeRetirement:
        return (
            RetireWorktree(worktrees=self.worktrees)
            .execute(RetireWorktreeParams(root=self.ROOT, worktree=self.PATH, branch=self.BRANCH))
            .retirement
        )

    @property
    def removed_nothing(self) -> bool:
        return not (self.worktrees.remove.called or self.worktrees.delete_branch.called)


class TestRetireWorktree:
    def test_a_tree_with_nothing_uncommitted_and_nothing_only_local_is_removed_with_its_branch(self) -> None:
        retiring = _Retiring()

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.RETIRED
        retiring.worktrees.remove.assert_called_once_with(root=retiring.ROOT, path=retiring.PATH)
        retiring.worktrees.delete_branch.assert_called_once_with(root=retiring.ROOT, branch=retiring.BRANCH)

    def test_the_tree_goes_before_its_branch_because_git_refuses_to_delete_a_branch_that_is_checked_out(self) -> None:
        retiring = _Retiring()
        calls: list[str] = []
        retiring.worktrees.remove.side_effect = lambda **_: calls.append("remove")
        retiring.worktrees.delete_branch.side_effect = lambda **_: calls.append("delete_branch")

        retiring.retire()

        assert calls == ["remove", "delete_branch"]

    def test_uncommitted_work_alone_keeps_the_tree_and_the_branch(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.has_uncommitted_work.return_value = True

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_UNCOMMITTED_WORK
        assert retiring.removed_nothing

    def test_commits_that_exist_only_locally_alone_keep_the_tree_and_the_branch(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.local_only_commits.return_value = 2

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS
        assert retiring.removed_nothing

    def test_when_both_conditions_fail_the_one_that_is_lost_for_good_is_the_one_reported(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.has_uncommitted_work.return_value = True
        retiring.worktrees.local_only_commits.return_value = 2

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_UNCOMMITTED_WORK

    def test_a_tree_that_cannot_be_asked_about_its_uncommitted_work_is_kept(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.has_uncommitted_work.side_effect = WorktreeRetirementError("git status failed")

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_UNVERIFIABLE
        assert retiring.removed_nothing

    def test_a_branch_that_cannot_be_asked_about_its_local_only_commits_is_kept(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.local_only_commits.side_effect = WorktreeRetirementError("git rev-list failed")

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_UNVERIFIABLE
        assert retiring.removed_nothing

    def test_a_tree_that_git_refuses_to_remove_is_kept_and_its_branch_is_left_alone(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.remove.side_effect = WorktreeRetirementError("git worktree remove failed")

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_REMOVAL_FAILED
        retiring.worktrees.delete_branch.assert_not_called()

    def test_a_branch_that_cannot_be_deleted_after_the_tree_went_is_reported_as_a_failed_removal(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.delete_branch.side_effect = WorktreeRetirementError("git branch -D failed")

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_REMOVAL_FAILED

    def test_a_path_with_no_tree_of_the_slice_on_it_asks_and_removes_nothing(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.is_mounted.return_value = False

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.NOT_MOUNTED
        retiring.worktrees.has_uncommitted_work.assert_not_called()
        retiring.worktrees.local_only_commits.assert_not_called()
        assert retiring.removed_nothing

    def test_a_tree_that_cannot_be_listed_is_kept_and_nothing_is_asked_or_removed(self) -> None:
        retiring = _Retiring()
        retiring.worktrees.is_mounted.side_effect = WorktreeRetirementError("git worktree list died")

        retirement = retiring.retire()

        assert retirement is WorktreeRetirement.KEPT_UNVERIFIABLE
        retiring.worktrees.has_uncommitted_work.assert_not_called()
        assert retiring.removed_nothing

    def test_the_mounting_is_asked_about_the_path_and_the_branch_of_the_slice(self) -> None:
        retiring = _Retiring()

        retiring.retire()

        retiring.worktrees.is_mounted.assert_called_once_with(
            root=retiring.ROOT, path=retiring.PATH, branch=retiring.BRANCH
        )

    def test_the_uncommitted_work_is_asked_of_the_tree_and_the_local_only_commits_of_the_branch(self) -> None:
        retiring = _Retiring()

        retiring.retire()

        retiring.worktrees.has_uncommitted_work.assert_called_once_with(path=retiring.PATH)
        retiring.worktrees.local_only_commits.assert_called_once_with(root=retiring.ROOT, branch=retiring.BRANCH)
