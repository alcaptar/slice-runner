from __future__ import annotations

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.step import Step


class DiscardedCallMother:
    @staticmethod
    def of_a_failed_call() -> DiscardedCall:
        return DiscardedCall(step=Step.VERIFY, cause=DiscardCause.FAILED_CALL, reason="claude: command not found")

    @staticmethod
    def of_an_incoherent_verdict() -> DiscardedCall:
        return DiscardedCall(
            step=Step.VERIFY,
            cause=DiscardCause.INCOHERENT_VERDICT,
            reason="a PASS with a finding of severity high contradicts the rubric",
        )

    @staticmethod
    def of_the_step(step: Step) -> DiscardedCall:
        return DiscardedCall(step=step, cause=DiscardCause.FAILED_CALL, reason="claude: command not found")

    @staticmethod
    def of_a_missing_structured_output() -> DiscardedCall:
        return DiscardedCall(
            step=Step.UNDERSTAND,
            cause=DiscardCause.NO_STRUCTURED_OUTPUT,
            reason="the harness envelope has no `structured_output`",
        )
