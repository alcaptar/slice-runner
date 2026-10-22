from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.domain.worktree_classifier import WorktreeClassifier
from slice_runner.domain.worktree_standing import WorktreeStanding

if TYPE_CHECKING:
    from slice_runner.domain.worktree_classification import WorktreeClassification
    from slice_runner.domain.worktrees import Worktrees


@dataclass(frozen=True, kw_only=True, slots=True)
class MountWorktreeParams:
    root: str
    worktree: str
    branch: str
    base: str
    expects_a_tree: bool = True


@dataclass(frozen=True, kw_only=True, slots=True)
class MountWorktreeResult:
    outcome: Outcome
    conflicting_path: str = ""


class MountWorktree:
    def __init__(self, *, worktrees: Worktrees) -> None:
        self._worktrees = worktrees

    def execute(self, params: MountWorktreeParams) -> MountWorktreeResult:
        if self._belongs_to_another_clone(params):
            return MountWorktreeResult(outcome=Outcome.WORKTREE_TAKEN, conflicting_path=params.worktree)

        self._worktrees.exclude(root=params.root, rule=SliceIdentity.worktrees_exclusion())
        self._worktrees.exclude(root=params.root, rule=DesignCapturesDirectory.exclusion())
        branch_exists = self._worktrees.branch_exists(root=params.root, name=params.branch)
        classification = WorktreeClassifier.of(
            listed=self._worktrees.listed(root=params.root),
            branch=params.branch,
            path=params.worktree,
            branch_exists=branch_exists,
        )

        return self._acting_on(classification, params, branch_exists=branch_exists)

    def _belongs_to_another_clone(self, params: MountWorktreeParams) -> bool:
        of_the_tree = self._worktrees.common_dir(path=params.worktree)

        return of_the_tree != "" and of_the_tree != self._worktrees.common_dir(path=params.root)

    def _acting_on(
        self, classification: WorktreeClassification, params: MountWorktreeParams, *, branch_exists: bool
    ) -> MountWorktreeResult:
        match classification.standing:
            case WorktreeStanding.MOUNTED:
                return self._reusing(params)
            case WorktreeStanding.ABSENT:
                self._creating_the_branch(params)
            case WorktreeStanding.BRANCH_ONLY:
                self._mounting_on_the_branch(params)
            case WorktreeStanding.STALE:
                self._worktrees.prune(root=params.root)
                if branch_exists:
                    self._mounting_on_the_branch(params)
                else:
                    self._creating_the_branch(params)
            case WorktreeStanding.TAKEN_ELSEWHERE | WorktreeStanding.FOREIGN_BRANCH:
                return MountWorktreeResult(
                    outcome=Outcome.WORKTREE_TAKEN, conflicting_path=classification.conflicting_path
                )

        return MountWorktreeResult(outcome=Outcome.DONE)

    @staticmethod
    def _reusing(params: MountWorktreeParams) -> MountWorktreeResult:
        if params.expects_a_tree:
            return MountWorktreeResult(outcome=Outcome.DONE)

        return MountWorktreeResult(outcome=Outcome.WORKTREE_LEFT_BEHIND, conflicting_path=params.worktree)

    def _creating_the_branch(self, params: MountWorktreeParams) -> None:
        self._worktrees.add_new_branch(root=params.root, path=params.worktree, branch=params.branch, base=params.base)

    def _mounting_on_the_branch(self, params: MountWorktreeParams) -> None:
        self._worktrees.add_on_branch(root=params.root, path=params.worktree, branch=params.branch)
