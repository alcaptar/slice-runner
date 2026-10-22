from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.run_state import RunState


class ClosingReason(StrEnum):
    CONTROLS = "controls"
    JUDGE = "judge"
    CI_RED = "ci-red"
    CI_INDETERMINATE = "ci-indeterminate"
    CI_CONFLICT = "ci-conflict"
    WORKTREE = "worktree"
    BUDGET = "budget"
    UNMEASURED_CALL = "unmeasured-call"

    @property
    def closes_as(self) -> RunState:
        match self:
            case ClosingReason.BUDGET | ClosingReason.UNMEASURED_CALL:
                return RunState.ABORTED
            case (
                ClosingReason.CONTROLS
                | ClosingReason.JUDGE
                | ClosingReason.CI_RED
                | ClosingReason.CI_INDETERMINATE
                | ClosingReason.CI_CONFLICT
                | ClosingReason.WORKTREE
            ):
                return RunState.BLOCKED

    @property
    def publishes_the_findings(self) -> bool:
        match self:
            case ClosingReason.JUDGE:
                return True
            case (
                ClosingReason.CONTROLS
                | ClosingReason.CI_RED
                | ClosingReason.CI_INDETERMINATE
                | ClosingReason.CI_CONFLICT
                | ClosingReason.WORKTREE
                | ClosingReason.BUDGET
                | ClosingReason.UNMEASURED_CALL
            ):
                return False
