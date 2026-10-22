from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.issue_label import IssueLabel


class RetiredIssueLabel(StrEnum):
    HYGIENE = "bloqueada:higiene"
    VERIFY = "bloqueada:verify"
    UNCHANGED_DIFF = "bloqueada:sin-cambios"
    LEFTOVER_WORKTREE = "bloqueada:worktree-sin-retirar"

    @property
    def replacement(self) -> IssueLabel:
        match self:
            case RetiredIssueLabel.HYGIENE:
                return IssueLabel.BLOCKED_CONTROLS
            case RetiredIssueLabel.VERIFY | RetiredIssueLabel.UNCHANGED_DIFF:
                return IssueLabel.BLOCKED_JUDGE
            case RetiredIssueLabel.LEFTOVER_WORKTREE:
                return IssueLabel.BLOCKED_WORKTREE
