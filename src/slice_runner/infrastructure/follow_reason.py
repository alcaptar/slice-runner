from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.infrastructure.follow_standing import FollowStanding


class FollowReason(StrEnum):
    CONTROLS = "controls"
    JUDGE = "judge"
    CI_RED = "ci-red"
    CI_INDETERMINATE = "ci-indeterminate"
    CI_CONFLICT = "ci-conflict"
    WORKTREE = "worktree"
    BUDGET = "budget"
    UNMEASURED_CALL = "unmeasured-call"

    @classmethod
    def of(cls, reason: ClosingReason) -> FollowReason:
        return cls(reason.value)

    def to_closing_reason(self) -> ClosingReason:
        return ClosingReason(self.value)

    @property
    def standing(self) -> FollowStanding:
        match self:
            case (
                FollowReason.CONTROLS
                | FollowReason.JUDGE
                | FollowReason.CI_RED
                | FollowReason.CI_INDETERMINATE
                | FollowReason.CI_CONFLICT
                | FollowReason.WORKTREE
            ):
                return FollowStanding.BLOCKED
            case FollowReason.BUDGET | FollowReason.UNMEASURED_CALL:
                return FollowStanding.ABORTED
