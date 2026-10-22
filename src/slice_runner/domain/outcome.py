from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.control_status import ControlStatus
from slice_runner.domain.cost_exhaustion import CostExhaustion
from slice_runner.domain.ruling import Ruling

if TYPE_CHECKING:
    from slice_runner.domain.control_outcome import ControlOutcome
    from slice_runner.domain.verdict import Verdict


class Outcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    HYGIENE_REJECTED = "hygiene-rejected"
    PENDING = "pending"
    INDETERMINATE = "indeterminate"
    DISCARDED = "discarded"
    OVER_BUDGET = "over-budget"
    CALL_NOT_MEASURED = "call-not-measured"
    CONFLICTING = "conflicting"
    CHANGES_REQUESTED = "changes-requested"
    UNCHANGED = "unchanged"
    WORKTREE_TAKEN = "worktree-taken"
    WORKTREE_LEFT_BEHIND = "worktree-left-behind"

    @classmethod
    def of_the_ci(cls, status: CiStatus) -> Outcome:
        match status:
            case CiStatus.GREEN:
                return cls.DONE
            case CiStatus.RED:
                return cls.FAILED
            case CiStatus.PENDING:
                return cls.PENDING
            case CiStatus.NO_CHECKS | CiStatus.UNKNOWN:
                return cls.INDETERMINATE

    @classmethod
    def of_the_verdict(cls, verdict: Verdict) -> Outcome:
        match verdict.ruling:
            case Ruling.FAIL:
                return cls.FAILED
            case Ruling.PASS:
                return cls.DONE

    @classmethod
    def of_the_controls(cls, outcomes: tuple[ControlOutcome, ...]) -> Outcome:
        if any(outcome.status is ControlStatus.RED for outcome in outcomes):
            return cls.FAILED
        if any(outcome.status is ControlStatus.UNKNOWN for outcome in outcomes):
            return cls.INDETERMINATE

        return cls.DONE

    @classmethod
    def of_the_catch_up(cls, outcome: BranchCatchUpOutcome) -> Outcome:
        match outcome:
            case BranchCatchUpOutcome.CAUGHT_UP:
                return cls.DONE
            case BranchCatchUpOutcome.CONFLICTING:
                return cls.CONFLICTING

    @classmethod
    def of_the_cost_exhaustion(cls, exhaustion: CostExhaustion, *, otherwise: Outcome) -> Outcome:
        match exhaustion:
            case CostExhaustion.WITHIN_BUDGET:
                return otherwise
            case CostExhaustion.CALL_UNMEASURED:
                return cls.CALL_NOT_MEASURED
            case CostExhaustion.TOTAL_EXCEEDED:
                return cls.OVER_BUDGET
