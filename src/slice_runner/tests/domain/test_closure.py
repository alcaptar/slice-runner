from __future__ import annotations

import pytest

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.exceptions import InvalidClosureError
from slice_runner.domain.run_state import RunState


class TestWhatAClosureRefuses:
    @pytest.mark.parametrize(
        ("state", "reason"),
        [
            (RunState.OPEN, ClosingReason.CONTROLS),
            (RunState.MERGED, ClosingReason.CI_RED),
            (RunState.BLOCKED, None),
            (RunState.ABORTED, None),
            (RunState.BLOCKED, ClosingReason.BUDGET),
            (RunState.BLOCKED, ClosingReason.UNMEASURED_CALL),
            (RunState.ABORTED, ClosingReason.CONTROLS),
            (RunState.ABORTED, ClosingReason.WORKTREE),
        ],
        ids=[
            "a-reason-on-an-open-run",
            "a-reason-on-a-merged-run",
            "a-blocked-run-without-a-reason",
            "an-aborted-run-without-a-reason",
            "an-abort-reason-on-a-blocked-run-budget",
            "an-abort-reason-on-a-blocked-run-unmeasured-call",
            "a-block-reason-on-an-aborted-run-controls",
            "a-block-reason-on-an-aborted-run-leftover-worktree",
        ],
    )
    def test_the_combination_is_rejected_when_it_is_built(self, state: RunState, reason: ClosingReason | None) -> None:
        with pytest.raises(InvalidClosureError):
            Closure(state=state, reason=reason)


class TestWhatAClosureAccepts:
    @pytest.mark.parametrize("reason", list(ClosingReason))
    def test_every_reason_closes_the_run_in_the_state_it_belongs_to(self, reason: ClosingReason) -> None:
        closure = Closure.because_of(reason)

        assert closure.reason is reason
        assert closure.state in (RunState.BLOCKED, RunState.ABORTED)

    def test_only_the_budget_and_the_unmeasured_call_abort_the_run(self) -> None:
        aborting = {reason for reason in ClosingReason if Closure.because_of(reason).state is RunState.ABORTED}

        assert aborting == {ClosingReason.BUDGET, ClosingReason.UNMEASURED_CALL}

    def test_an_open_and_a_merged_run_carry_no_reason(self) -> None:
        assert (Closure.open().reason, Closure.merged().reason) == (None, None)
