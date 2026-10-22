from __future__ import annotations

from dataclasses import replace

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.halt import Halt
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.tests.conductor import Conductor
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother
from slice_runner.tests.mothers.rejection_mother import RejectionMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.select_slice_result_mother import SelectSliceResultMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_SUBISSUE = SubIssueMother.pending().number
_BRANCH = SubIssueMother.pending().branch


class _Merging:
    @staticmethod
    def conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

    @staticmethod
    def published(conductor: Conductor, retirement: WorktreeRetirement) -> None:
        conductor.repository.publish_kept_worktree.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, path=Conductor.WORKTREE, retirement=retirement
        )


class TestConductSliceRetiringTheWorktreeOfAMergedRun(_Merging):
    def test_a_merged_run_with_nothing_to_lose_leaves_neither_its_worktree_nor_its_local_branch(self) -> None:
        conductor = self.conductor()

        result = conductor.conduct()

        assert result.closure == Closure.merged()
        conductor.worktrees.remove.assert_called_once_with(root=Conductor.ROOT, path=Conductor.WORKTREE)
        conductor.worktrees.delete_branch.assert_called_once_with(root=Conductor.ROOT, branch=_BRANCH)

    def test_a_retired_worktree_publishes_no_comment_because_nothing_is_left_to_tell(self) -> None:
        conductor = self.conductor()

        conductor.conduct()

        conductor.repository.publish_kept_worktree.assert_not_called()
        assert conductor.closed.worktree_retirement is WorktreeRetirement.RETIRED

    def test_the_retirement_is_asked_about_the_tree_the_run_mounted_and_not_about_the_root(self) -> None:
        conductor = self.conductor()

        conductor.conduct()

        conductor.worktrees.has_uncommitted_work.assert_called_once_with(path=Conductor.WORKTREE)
        conductor.worktrees.local_only_commits.assert_called_once_with(root=Conductor.ROOT, branch=_BRANCH)

    def test_uncommitted_work_alone_keeps_the_worktree_and_the_branch(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.has_uncommitted_work.return_value = True

        conductor.conduct()

        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.delete_branch.called
        self.published(conductor, WorktreeRetirement.KEPT_UNCOMMITTED_WORK)

    def test_commits_that_exist_only_locally_alone_keep_the_worktree_and_the_branch(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.local_only_commits.return_value = 3

        conductor.conduct()

        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.delete_branch.called
        self.published(conductor, WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS)

    def test_a_port_that_fails_when_asked_about_uncommitted_work_keeps_the_worktree(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.has_uncommitted_work.side_effect = WorktreeRetirementError("git status died")

        conductor.conduct()

        assert not conductor.worktrees.remove.called
        self.published(conductor, WorktreeRetirement.KEPT_UNVERIFIABLE)

    def test_a_port_that_fails_when_asked_about_local_only_commits_keeps_the_worktree(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.local_only_commits.side_effect = WorktreeRetirementError("git rev-list died")

        conductor.conduct()

        assert not conductor.worktrees.remove.called
        self.published(conductor, WorktreeRetirement.KEPT_UNVERIFIABLE)

    @pytest.mark.parametrize(
        "keeping",
        [
            {"is_mounted": WorktreeRetirementError("died")},
            {"has_uncommitted_work": True},
            {"local_only_commits": 1},
            {"has_uncommitted_work": WorktreeRetirementError("died")},
            {"local_only_commits": WorktreeRetirementError("died")},
            {"remove": WorktreeRetirementError("git refused")},
            {"delete_branch": WorktreeRetirementError("git refused")},
        ],
        ids=[
            "unverifiable-listing",
            "uncommitted",
            "local-only",
            "unverifiable-status",
            "unverifiable-count",
            "remove-failed",
            "branch-failed",
        ],
    )
    def test_a_worktree_that_could_not_be_retired_never_changes_the_verdict_of_a_merged_run(
        self, keeping: dict[str, object]
    ) -> None:
        conductor = self.conductor()
        for method, behaviour in keeping.items():
            double = getattr(conductor.worktrees, method)
            if isinstance(behaviour, Exception):
                double.side_effect = behaviour
            else:
                double.return_value = behaviour

        result = conductor.conduct()

        assert (result.halt, result.closure) == (Halt.RUN_CLOSED, Closure.merged())
        assert conductor.closed.closure == Closure.merged()
        conductor.repository.clear_run.assert_called_once_with(repo=Conductor.REPO, issue=_SUBISSUE)
        assert conductor.close.execute.call_count == 1
        assert conductor.closed.worktree_retirement.kept

    def test_a_tree_git_refuses_to_remove_is_kept_and_the_comment_says_the_removal_failed(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.remove.side_effect = WorktreeRetirementError("git refused")

        conductor.conduct()

        assert not conductor.worktrees.delete_branch.called
        self.published(conductor, WorktreeRetirement.KEPT_REMOVAL_FAILED)

    def test_the_closure_handed_to_the_log_carries_where_the_kept_worktree_stayed_and_why(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.has_uncommitted_work.return_value = True

        conductor.conduct()

        assert conductor.closed.worktree == Conductor.WORKTREE
        assert conductor.closed.worktree_retirement is WorktreeRetirement.KEPT_UNCOMMITTED_WORK

    def test_a_merged_run_with_no_tree_on_its_path_asks_nothing_and_removes_nothing(self) -> None:
        conductor = self.conductor()
        conductor.worktrees.is_mounted.return_value = False

        conductor.conduct()

        assert not conductor.worktrees.has_uncommitted_work.called
        assert not conductor.worktrees.remove.called
        conductor.repository.publish_kept_worktree.assert_not_called()
        assert conductor.closed.worktree_retirement is WorktreeRetirement.NOT_MOUNTED

    def test_a_worktree_given_by_hand_is_not_the_programs_to_retire(self) -> None:
        conductor = self.conductor()

        conductor.conduct(worktree=Conductor.WORKTREE)

        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.delete_branch.called
        assert conductor.closed.worktree_retirement is WorktreeRetirement.NOT_MOUNTED

    def test_the_tree_is_retired_before_the_row_is_written_so_the_row_tells_what_happened(self) -> None:
        conductor = self.conductor()
        order: list[str] = []
        conductor.worktrees.remove.side_effect = lambda **_: order.append("remove")
        conductor.metrics.record.side_effect = lambda _: order.append("record")

        conductor.conduct()

        assert order == ["remove", "record"]


class TestConductSliceTheEndingsThatKeepTheWorktree(_Merging):
    def test_a_run_blocked_after_delivering_keeps_its_worktree_and_its_branch_without_asking_anything(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.running_the_controls()),
            budgets=Budgets(control_retries=0),
        )
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)
        assert not conductor.worktrees.has_uncommitted_work.called
        assert not conductor.worktrees.local_only_commits.called
        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.delete_branch.called

    def test_a_blocked_run_tells_where_its_worktree_stayed_and_that_it_stays_to_resume(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.running_the_controls()),
            budgets=Budgets(control_retries=0),
        )
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        self.published(conductor, WorktreeRetirement.KEPT_FOR_RESUMING)
        assert conductor.closed.worktree_retirement is WorktreeRetirement.KEPT_FOR_RESUMING

    def test_a_run_aborted_after_touching_code_keeps_its_worktree_and_its_branch(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))
        conductor.implement.execute.side_effect = RejectionMother.envelope_nobody_could_parse()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.UNMEASURED_CALL)
        assert not conductor.worktrees.has_uncommitted_work.called
        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.delete_branch.called
        self.published(conductor, WorktreeRetirement.KEPT_FOR_RESUMING)


class TestConductSliceWhenATreeIsFoundThatNobodyExpected(_Merging):
    @staticmethod
    def _after_an_abort_that_left_its_tree() -> Conductor:
        reopened = replace(RunMother.implementing(), tree_unexpected=True)
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(reopened))
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=Conductor.WORKTREE, branch=_BRANCH),
        )
        conductor.worktrees.branch_exists.return_value = True

        return conductor

    def test_a_tree_an_abort_before_touching_code_could_not_retire_blocks_the_next_invocation_of_that_slice(
        self,
    ) -> None:
        conductor = self._after_an_abort_that_left_its_tree()

        result = conductor.conduct()

        assert (result.halt, result.closure) == (Halt.RUN_CLOSED, Closure.because_of(ClosingReason.WORKTREE))
        assert result.conflicting_path == Conductor.WORKTREE

    def test_a_tree_left_by_a_stop_of_the_prechecks_is_reused_by_the_next_invocation(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=Conductor.WORKTREE, branch=_BRANCH),
        )

        result = conductor.conduct()

        assert result.closure != Closure.because_of(ClosingReason.WORKTREE)
        assert not conductor.worktrees.add_new_branch.called
        assert not conductor.worktrees.add_on_branch.called
        assert conductor.check_sources.execute.call_count == 1

    def test_the_next_invocation_neither_mounts_over_the_old_tree_nor_reuses_it(self) -> None:
        conductor = self._after_an_abort_that_left_its_tree()

        conductor.conduct()

        assert not conductor.worktrees.add_new_branch.called
        assert not conductor.worktrees.add_on_branch.called
        assert not conductor.worktrees.prune.called
        assert conductor.check_sources.execute.call_count == 0

    def test_the_blocked_slice_is_labelled_so_it_is_not_picked_up_again_on_its_own(self) -> None:
        conductor = self._after_an_abort_that_left_its_tree()

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_WORKTREE,
        )
        assert conductor.closed.closure == Closure.because_of(ClosingReason.WORKTREE)

    def test_the_closing_names_the_path_and_leaves_the_tree_for_a_person_to_resolve(self) -> None:
        conductor = self._after_an_abort_that_left_its_tree()

        conductor.conduct()

        self.published(conductor, WorktreeRetirement.KEPT_UNEXPECTED)
        assert not conductor.worktrees.remove.called
        assert not conductor.worktrees.has_uncommitted_work.called

    def test_a_blocked_run_reopened_by_the_retry_subcommand_reuses_the_tree_it_kept(self) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_JUDGE, RunMother.blocked_on_verify())
        reopened = replace(blocked, run=RunMother.implementing(), label=IssueLabel.IN_PROGRESS)
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=reopened))

        result = conductor.conduct()

        assert result.closure != Closure.because_of(ClosingReason.WORKTREE)
        assert not conductor.worktrees.add_new_branch.called
        assert not conductor.worktrees.add_on_branch.called
        assert conductor.implement.execute.call_count == 1

    @staticmethod
    def _reopened_by_the_retry_subcommand_after_a_leftover() -> Conductor:
        reopened = replace(RunMother.implementing(), tree_unexpected=True)

        return Conductor(chosen=SelectSliceResultMother.resumed_at(reopened))

    def test_a_run_reopened_by_the_retry_subcommand_after_a_leftover_finds_the_old_tree_and_blocks_again(self) -> None:
        conductor = self._reopened_by_the_retry_subcommand_after_a_leftover()
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=Conductor.WORKTREE, branch=_BRANCH),
        )
        conductor.worktrees.branch_exists.return_value = True

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.WORKTREE)
        assert conductor.implement.execute.call_count == 0

    def test_a_run_reopened_by_the_retry_subcommand_with_no_tree_in_the_way_mounts_one_and_expects_it_from_then_on(
        self,
    ) -> None:
        conductor = self._reopened_by_the_retry_subcommand_after_a_leftover()
        conductor.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(),)

        conductor.conduct()

        assert conductor.worktrees.add_new_branch.called or conductor.worktrees.add_on_branch.called
        assert conductor.repository.write_run.call_args_list[0].kwargs["run"].tree_unexpected is False

    def test_a_worktree_given_by_hand_is_expected_so_it_is_never_taken_for_a_leftover(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path="/trees/by-hand", branch=_BRANCH),
        )

        result = conductor.conduct(worktree="/trees/by-hand")

        assert result.closure != Closure.because_of(ClosingReason.WORKTREE)


class TestConductSliceRetiringTheWorktreeOfAMergeMissedBetweenInvocations:
    @staticmethod
    def _conductor() -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(dangling=(SubIssueMother.dangling(),)))
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=Conductor.WORKTREE, branch=_BRANCH),
        )

        return conductor

    def test_a_merge_reconciled_late_retires_the_tree_that_was_left_from_the_derived_path(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.worktrees.remove.assert_any_call(root=Conductor.ROOT, path=Conductor.WORKTREE)
        conductor.worktrees.delete_branch.assert_any_call(root=Conductor.ROOT, branch=_BRANCH)

    def test_a_merge_reconciled_late_keeps_a_tree_with_uncommitted_work_and_still_closes_as_merged(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.has_uncommitted_work.return_value = True

        conductor.conduct()

        assert not conductor.worktrees.remove.called
        first = conductor.metrics.record.call_args_list[0].args[0]
        assert first.closure == Closure.merged()
        assert first.worktree_retirement is WorktreeRetirement.KEPT_UNCOMMITTED_WORK
        conductor.repository.clear_run.assert_any_call(repo=Conductor.REPO, issue=SubIssueMother.dangling().number)
