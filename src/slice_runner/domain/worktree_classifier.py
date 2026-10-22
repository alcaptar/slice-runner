from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.worktree_classification import WorktreeClassification
from slice_runner.domain.worktree_standing import WorktreeStanding

if TYPE_CHECKING:
    from slice_runner.domain.listed_worktree import ListedWorktree


class WorktreeClassifier:
    @classmethod
    def of(
        cls, *, listed: tuple[ListedWorktree, ...], branch: str, path: str, branch_exists: bool
    ) -> WorktreeClassification:
        holder = cls._holding(listed, branch)
        if holder is not None:
            return cls._of_the_holder(holder, path=path)

        registered = cls._registered_at(listed, path)
        if registered is not None:
            if registered.prunable:
                return WorktreeClassification(standing=WorktreeStanding.STALE)

            return WorktreeClassification(standing=WorktreeStanding.FOREIGN_BRANCH, conflicting_path=registered.path)
        if branch_exists:
            return WorktreeClassification(standing=WorktreeStanding.BRANCH_ONLY)

        return WorktreeClassification(standing=WorktreeStanding.ABSENT)

    @staticmethod
    def _of_the_holder(holder: ListedWorktree, *, path: str) -> WorktreeClassification:
        if holder.main:
            return WorktreeClassification(standing=WorktreeStanding.TAKEN_ELSEWHERE, conflicting_path=holder.path)
        if holder.prunable:
            return WorktreeClassification(standing=WorktreeStanding.STALE)
        if holder.path == path:
            return WorktreeClassification(standing=WorktreeStanding.MOUNTED)

        return WorktreeClassification(standing=WorktreeStanding.TAKEN_ELSEWHERE, conflicting_path=holder.path)

    @staticmethod
    def _holding(listed: tuple[ListedWorktree, ...], branch: str) -> ListedWorktree | None:
        return next((entry for entry in listed if entry.branch == branch), None)

    @staticmethod
    def _registered_at(listed: tuple[ListedWorktree, ...], path: str) -> ListedWorktree | None:
        return next((entry for entry in listed if entry.path == path), None)
