from __future__ import annotations

from typing import ClassVar
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.mount_worktree import MountWorktree, MountWorktreeParams, MountWorktreeResult
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.worktrees import Worktrees
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class _Mounting:
    ROOT: ClassVar[str] = ListedWorktreeMother.ROOT
    BASE: ClassVar[str] = ListedWorktreeMother.BASE
    COMMON_DIR: ClassVar[str] = "/repos/slice-runner/.git"
    BRANCH: ClassVar[str] = SubIssueMother.pending().branch
    DERIVED: ClassVar[str] = SubIssueMother.pending().slice_id.worktree_under(ROOT)
    ELSEWHERE: ClassVar[str] = "/somewhere/else/05-prechecks-deterministas"

    def __init__(self) -> None:
        self.worktrees: Mock = create_autospec(Worktrees, spec_set=True, instance=True)
        self.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(),)
        self.worktrees.branch_exists.return_value = False
        self.worktrees.common_dir.return_value = self.COMMON_DIR

    def listing(self, *listed: object) -> None:
        self.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(), *listed)

    def mount(self, *, worktree: str | None = None, expects_a_tree: bool = True) -> MountWorktreeResult:
        return MountWorktree(worktrees=self.worktrees).execute(
            MountWorktreeParams(
                root=self.ROOT,
                worktree=worktree or self.DERIVED,
                branch=self.BRANCH,
                base=self.BASE,
                expects_a_tree=expects_a_tree,
            )
        )

    @property
    def changed_nothing(self) -> bool:
        return not (
            self.worktrees.add_new_branch.called or self.worktrees.add_on_branch.called or self.worktrees.prune.called
        )


class TestMountWorktree:
    def test_the_directory_of_the_design_captures_is_excluded_from_git_when_the_worktree_is_mounted(self) -> None:
        mounting = _Mounting()

        mounting.mount()

        mounting.worktrees.exclude.assert_any_call(root=mounting.ROOT, rule="/.design-captures/")

    def test_with_nothing_mounted_and_no_branch_it_creates_both_from_the_base(self) -> None:
        mounting = _Mounting()

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        mounting.worktrees.add_new_branch.assert_called_once_with(
            root=mounting.ROOT, path=mounting.DERIVED, branch=mounting.BRANCH, base=mounting.BASE
        )
        mounting.worktrees.add_on_branch.assert_not_called()
        mounting.worktrees.prune.assert_not_called()

    def test_with_the_branch_already_there_but_no_worktree_it_mounts_on_that_branch(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        mounting.worktrees.add_on_branch.assert_called_once_with(
            root=mounting.ROOT, path=mounting.DERIVED, branch=mounting.BRANCH
        )
        mounting.worktrees.add_new_branch.assert_not_called()

    def test_with_the_worktree_already_on_its_branch_it_touches_nothing(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.DERIVED, branch=mounting.BRANCH))

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        assert mounting.changed_nothing

    def test_the_main_clone_on_the_base_is_not_taken_for_the_worktree_of_a_slice(self) -> None:
        mounting = _Mounting()
        mounting.listing()

        mounting.mount()

        mounting.worktrees.add_new_branch.assert_called_once()

    def test_the_branch_checked_out_in_another_worktree_closes_naming_where_the_conflict_is(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.ELSEWHERE, branch=mounting.BRANCH))

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.ELSEWHERE)
        assert mounting.changed_nothing

    def test_the_branch_checked_out_in_the_main_clone_closes_naming_the_clone(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(on=mounting.BRANCH),)

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.ROOT)
        assert mounting.changed_nothing

    def test_the_main_clone_on_the_branch_of_the_slice_is_not_taken_for_its_worktree_even_when_passed_as_the_path(
        self,
    ) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(on=mounting.BRANCH),)

        result = mounting.mount(worktree=mounting.ROOT)

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.ROOT)
        assert mounting.changed_nothing

    def test_a_registered_worktree_whose_directory_is_gone_is_pruned_before_mounting_on_its_branch(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(
            ListedWorktreeMother.whose_directory_was_deleted(path=mounting.DERIVED, branch=mounting.BRANCH)
        )

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        assert [call[0] for call in mounting.worktrees.method_calls if call[0] in ("prune", "add_on_branch")] == [
            "prune",
            "add_on_branch",
        ]

    def test_a_registered_worktree_whose_directory_is_gone_is_told_apart_from_nothing_mounted(self) -> None:
        stale = _Mounting()
        stale.worktrees.branch_exists.return_value = True
        stale.listing(ListedWorktreeMother.whose_directory_was_deleted(path=stale.DERIVED, branch=stale.BRANCH))
        nothing = _Mounting()
        nothing.worktrees.branch_exists.return_value = True

        stale.mount()
        nothing.mount()

        assert (stale.worktrees.prune.called, nothing.worktrees.prune.called) == (True, False)

    def test_a_deleted_worktree_on_a_foreign_branch_is_pruned_and_the_branch_is_created(self) -> None:
        mounting = _Mounting()
        mounting.listing(
            ListedWorktreeMother.whose_directory_was_deleted(path=mounting.DERIVED, branch="slice/00-other")
        )

        mounting.mount()

        mounting.worktrees.prune.assert_called_once_with(root=mounting.ROOT)
        mounting.worktrees.add_new_branch.assert_called_once()

    def test_a_tree_mounted_by_hand_elsewhere_on_the_derived_branch_is_recognised_and_left_alone(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.ELSEWHERE, branch=mounting.BRANCH))

        result = mounting.mount(worktree=mounting.ELSEWHERE)

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        assert mounting.changed_nothing

    def test_a_tree_mounted_by_hand_on_a_foreign_branch_closes_naming_its_path(self) -> None:
        mounting = _Mounting()
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.ELSEWHERE, branch="slice/00-other"))

        result = mounting.mount(worktree=mounting.ELSEWHERE)

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.ELSEWHERE)
        assert mounting.changed_nothing

    def test_a_detached_tree_at_the_requested_path_closes_instead_of_being_taken_over(self) -> None:
        mounting = _Mounting()
        mounting.listing(ListedWorktreeMother.detached(path=mounting.DERIVED))

        result = mounting.mount()

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.DERIVED)
        assert mounting.changed_nothing

    def test_a_tree_of_another_clone_given_with_the_root_of_this_one_mounts_nothing(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.common_dir.side_effect = lambda *, path: (
            "/other/clone/.git" if path == mounting.ELSEWHERE else mounting.COMMON_DIR
        )

        result = mounting.mount(worktree=mounting.ELSEWHERE)

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=mounting.ELSEWHERE)
        assert mounting.changed_nothing

    def test_a_path_that_is_not_in_any_repo_yet_is_not_taken_for_a_foreign_clone(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.common_dir.side_effect = lambda *, path: (
            "" if path == mounting.DERIVED else mounting.COMMON_DIR
        )

        result = mounting.mount()

        assert result.outcome is Outcome.DONE

    def test_it_ignores_the_directory_of_the_worktrees_in_the_clone_before_listing_anything(self) -> None:
        mounting = _Mounting()

        mounting.mount()

        called = [call[0] for call in mounting.worktrees.method_calls]
        mounting.worktrees.exclude.assert_any_call(root=mounting.ROOT, rule="/.worktrees/")
        assert mounting.worktrees.exclude.call_count == 2
        assert called.index("exclude") < called.index("listed")


class TestMountWorktreeFindingATreeNobodyExpected:
    def test_a_tree_already_on_its_branch_that_nobody_expected_is_reported_as_left_behind_with_its_path(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.DERIVED, branch=mounting.BRANCH))

        result = mounting.mount(expects_a_tree=False)

        assert result == MountWorktreeResult(outcome=Outcome.WORKTREE_LEFT_BEHIND, conflicting_path=mounting.DERIVED)

    def test_a_tree_that_nobody_expected_is_neither_reused_nor_mounted_over(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.DERIVED, branch=mounting.BRANCH))

        mounting.mount(expects_a_tree=False)

        assert mounting.changed_nothing

    def test_a_tree_that_was_expected_is_reused_as_before(self) -> None:
        mounting = _Mounting()
        mounting.worktrees.branch_exists.return_value = True
        mounting.listing(ListedWorktreeMother.mounted(path=mounting.DERIVED, branch=mounting.BRANCH))

        result = mounting.mount(expects_a_tree=True)

        assert result == MountWorktreeResult(outcome=Outcome.DONE)

    def test_nothing_mounted_is_mounted_whether_a_tree_was_expected_or_not(self) -> None:
        mounting = _Mounting()

        result = mounting.mount(expects_a_tree=False)

        assert result == MountWorktreeResult(outcome=Outcome.DONE)
        mounting.worktrees.add_new_branch.assert_called_once()
