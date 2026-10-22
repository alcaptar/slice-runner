from __future__ import annotations

import pytest

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.step import Step


class TestTheLabelOfEveryClosure:
    @pytest.mark.parametrize(
        ("reason", "label"),
        [
            (ClosingReason.CONTROLS, "bloqueada:controles"),
            (ClosingReason.JUDGE, "bloqueada:juez"),
            (ClosingReason.CI_RED, "bloqueada:ci-roja"),
            (ClosingReason.CI_INDETERMINATE, "bloqueada:ci-indeterminada"),
            (ClosingReason.CI_CONFLICT, "bloqueada:conflicto"),
            (ClosingReason.WORKTREE, "bloqueada:worktree"),
            (ClosingReason.BUDGET, "abortada:presupuesto"),
            (ClosingReason.UNMEASURED_CALL, "abortada:llamada-no-medida"),
        ],
    )
    def test_the_label_is_the_one_the_closure_wrote_before_the_state_was_split(
        self, reason: ClosingReason, label: str
    ) -> None:
        assert IssueLabel.of(closure=Closure.because_of(reason), step=Step.AWAIT_CI) == IssueLabel(label)

    @pytest.mark.parametrize("reason", list(ClosingReason))
    def test_the_label_reads_back_as_the_closure_that_wrote_it(self, reason: ClosingReason) -> None:
        closure = Closure.because_of(reason)
        label = IssueLabel.of(closure=closure, step=Step.AWAIT_CI)

        assert label is not None
        assert label.closed_as == closure
