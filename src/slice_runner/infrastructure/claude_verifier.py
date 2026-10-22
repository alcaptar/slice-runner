from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.domain.verification import Verification
from slice_runner.domain.verifier import Verifier
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner


class ClaudeVerifier(Verifier):
    def __init__(self, *, calls: HarnessInvocationRunner, reader: SourceReader) -> None:
        self._calls = calls
        self._reader = reader

    def verify(self, judge: Judge, review: SliceUnderReview) -> Verification:
        invocation = JudgeInvocation(judge=judge, review=review, reader=self._reader)
        envelope = self._calls.call(
            invocation,
            step=Step.VERIFY,
            subject=HarnessCallSubject(
                coordinates=SliceCoordinates(
                    repo=review.repo, issue=review.issue, slice_id=CanonicalSliceId.of_text(review.slice_id)
                ),
                worktree=review.worktree,
            ),
        )
        with envelope.measuring():
            verdict = VerdictPayload.from_dict(envelope.structured()).to_domain()

        return Verification(
            verdict=verdict,
            spend=envelope.to_domain(),
            session=envelope.session_id,
            denied_reads=tuple(denial.denied_action for denial in envelope.permission_denials),
        )
