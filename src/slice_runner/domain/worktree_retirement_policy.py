from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closing_worktree import ClosingWorktree
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.domain.worktree_retirement import WorktreeRetirement

if TYPE_CHECKING:
    from slice_runner.domain.closure import Closure
    from slice_runner.domain.run import Run


class WorktreeRetirementPolicy:
    @classmethod
    def of_the_closing(cls, *, closure: Closure, step: Step, tree_left_behind: bool) -> ClosingWorktree:
        match closure.state:
            case RunState.MERGED:
                return ClosingWorktree.RETIRE
            case RunState.ABORTED:
                return cls._of_the_aborted(step)
            case RunState.OPEN:
                return ClosingWorktree.KEEP_FOR_RESUMING
            case RunState.BLOCKED:
                return cls._of_the_blocked(closure.reason, tree_left_behind=tree_left_behind)

    @classmethod
    def of(cls, *, uncommitted: bool, local_only_commits: int) -> WorktreeRetirement:
        if uncommitted:
            return WorktreeRetirement.KEPT_UNCOMMITTED_WORK
        if local_only_commits > 0:
            return WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS

        return WorktreeRetirement.RETIRED

    @classmethod
    def expects_a_tree(cls, *, label: IssueLabel | None, run: Run | None) -> bool:
        if run is not None and run.tree_unexpected:
            return False
        if label is IssueLabel.PENDING:
            return True
        if run is None:
            return False
        closed = label.closed_as if label is not None else None
        if closed is None:
            return True

        match cls.of_the_closing(closure=closed, step=run.step, tree_left_behind=False):
            case ClosingWorktree.RETIRE | ClosingWorktree.UNEXPECTED:
                return False
            case ClosingWorktree.KEEP_FOR_RESUMING | ClosingWorktree.NOT_OURS:
                return True

    @staticmethod
    def _of_the_blocked(reason: ClosingReason | None, *, tree_left_behind: bool) -> ClosingWorktree:
        match reason:
            case ClosingReason.WORKTREE:
                return ClosingWorktree.UNEXPECTED if tree_left_behind else ClosingWorktree.NOT_OURS
            case (
                None
                | ClosingReason.CONTROLS
                | ClosingReason.JUDGE
                | ClosingReason.CI_RED
                | ClosingReason.CI_INDETERMINATE
                | ClosingReason.CI_CONFLICT
                | ClosingReason.BUDGET
                | ClosingReason.UNMEASURED_CALL
            ):
                return ClosingWorktree.KEEP_FOR_RESUMING

    @staticmethod
    def _of_the_aborted(step: Step) -> ClosingWorktree:
        match step:
            case Step.MOUNT_WORKTREE | Step.UNDERSTAND:
                return ClosingWorktree.RETIRE
            case (
                Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.AWAIT_CI
                | Step.CATCH_UP
                | Step.AWAIT_MERGE
            ):
                return ClosingWorktree.KEEP_FOR_RESUMING
