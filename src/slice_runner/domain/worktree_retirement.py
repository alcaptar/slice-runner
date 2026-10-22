from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.closing_worktree import ClosingWorktree


class WorktreeRetirement(StrEnum):
    RETIRED = "retired"
    KEPT_UNCOMMITTED_WORK = "kept-uncommitted-work"
    KEPT_LOCAL_ONLY_COMMITS = "kept-local-only-commits"
    KEPT_UNVERIFIABLE = "kept-unverifiable"
    KEPT_REMOVAL_FAILED = "kept-removal-failed"
    KEPT_FOR_RESUMING = "kept-for-resuming"
    KEPT_UNEXPECTED = "kept-unexpected"
    NOT_MOUNTED = "not-mounted"

    @property
    def kept(self) -> bool:
        match self:
            case WorktreeRetirement.RETIRED | WorktreeRetirement.NOT_MOUNTED:
                return False
            case (
                WorktreeRetirement.KEPT_UNCOMMITTED_WORK
                | WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS
                | WorktreeRetirement.KEPT_UNVERIFIABLE
                | WorktreeRetirement.KEPT_REMOVAL_FAILED
                | WorktreeRetirement.KEPT_FOR_RESUMING
                | WorktreeRetirement.KEPT_UNEXPECTED
            ):
                return True

    @classmethod
    def without_retiring(cls, closing: ClosingWorktree) -> WorktreeRetirement:
        match closing:
            case ClosingWorktree.RETIRE | ClosingWorktree.NOT_OURS:
                return cls.NOT_MOUNTED
            case ClosingWorktree.KEEP_FOR_RESUMING:
                return cls.KEPT_FOR_RESUMING
            case ClosingWorktree.UNEXPECTED:
                return cls.KEPT_UNEXPECTED
