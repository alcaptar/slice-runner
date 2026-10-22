from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import InvalidVerdictError, MalformedSliceIdError, MissingStructuredOutputError
from slice_runner.domain.ruling import Ruling
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.tests.doubles import (
    RecordedActivityLog,
    RecordedProcess,
    RecordedSourceReader,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
)
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process

_JUDGE = JudgeMother.adversarial()
_READER = RecordedSourceReader()


class Calling:
    @staticmethod
    def _calls(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> HarnessInvocationRunner:
        return HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=RecordedTurnLog(),
                activity=RecordedActivityLog(),
                spend_log=RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )


class TestTheVerdictOfARecordedCall(Calling):
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.JUDGE_RECORDED)
    def test_the_envelope_of_both_real_calls_is_read_whole_from_structured_output(self, recorded: str) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(recorded))

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        assert verification.verdict.ruling is Ruling.FAIL
        assert len(verification.verdict.findings) == 4

    def test_the_first_finding_of_the_recorded_call_arrives_whole(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        first = verification.verdict.findings[0]
        assert (first.rule, first.path, first.line) == ("convenciones", "mod.py", 11)


class TestWhereTheProcessRuns(Calling):
    def test_the_worktree_becomes_the_working_directory_of_the_process_and_not_the_conductors(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(_JUDGE, review)

        assert process.cwd == review.worktree


class TestHowTheJudgeIsCalled(Calling):
    def test_the_prompt_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(_JUDGE, review)

        assert process.stdin == JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text
        assert process.stdin not in process.argv

    def test_the_judge_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        assert process.calls == 1


class TestWhatTheJudgeCallCost(Calling):
    def test_the_spend_of_the_call_comes_back_with_the_verdict_because_the_judge_is_not_free(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.spend == HarnessSpendMother.of_the_judge_call()


class TestWhatTheJudgeCallWasIdentifiedBy(Calling):
    def test_the_session_of_the_call_comes_back_with_the_verdict_because_it_is_what_ties_this_row_to_calls_jsonl(
        self,
    ) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.session == HarnessEnvelopeMother.SESSION_OF_THE_JUDGE


class TestWhenTheJudgeAnswersSomethingIncoherent(Calling):
    def test_the_spend_survives_the_rejection_so_the_discarded_call_still_counts(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding())
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incoherent))

        with pytest.raises(InvalidVerdictError) as rejection:
            ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
                _JUDGE, SliceUnderReviewMother.of_the_slice()
            )

        assert rejection.value.spend == HarnessSpendMother.of_the_judge_call()


class TestWhenTheEnvelopeHasNoStructuredOutput(Calling):
    def test_the_spend_survives_the_rejection_so_the_discarded_call_still_counts(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.without_structured_output())

        with pytest.raises(MissingStructuredOutputError) as rejection:
            ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
                _JUDGE, SliceUnderReviewMother.of_the_slice()
            )

        assert rejection.value.spend == HarnessSpendMother.of_the_judge_call()


class TestTheCallSubjectComesFromTheReviewsOwnFields(Calling):
    def test_the_trace_carries_the_reviews_own_repo_issue_and_slice_id_and_not_a_crossed_field(self) -> None:
        trace = RecordedTrace()
        review = SliceUnderReviewMother.of_the_slice()

        ClaudeVerifier(
            calls=self._calls(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace), reader=_READER
        ).verify(_JUDGE, review)

        recorded = trace.calls[0]
        assert (recorded.coordinates.repo, recorded.coordinates.issue, recorded.coordinates.slice_id.text) == (
            review.repo,
            review.issue,
            review.slice_id,
        )

    def test_the_tool_use_recording_carries_the_reviews_own_worktree_and_slice_id(self) -> None:
        tool_uses = RecordedToolUseRecorder()
        review = SliceUnderReviewMother.of_the_slice()

        ClaudeVerifier(
            calls=self._calls(RecordedProcess(HarnessEnvelopeMother.recorded()), tool_uses=tool_uses), reader=_READER
        ).verify(_JUDGE, review)

        recorded = tool_uses.calls[0]
        assert (recorded.worktree, recorded.slice_id) == (review.worktree, review.slice_id)


class TestASliceIdThatIsNotCanonical(Calling):
    def test_a_slice_id_that_a_person_typed_wrong_is_rejected_before_any_call_is_made(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        review = SliceUnderReviewMother.of_the_slice(slice_id="01")

        with pytest.raises(MalformedSliceIdError):
            ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(_JUDGE, review)

        assert process.calls == 0


class TestWhatTheHarnessDeniedTheJudge(Calling):
    def test_a_denied_read_comes_back_with_the_verdict_so_nobody_has_to_reopen_the_envelope(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read())

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.denied_reads == (f"Read {HarnessEnvelopeMother.DENIED_READ}",)

    def test_the_verdict_is_still_the_judges_because_a_denied_read_is_not_a_veto(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read(JudgeVerdictMother.passing()))

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.verdict.ruling is Ruling.PASS

    def test_an_envelope_with_no_denials_leaves_nothing_to_warn_about(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(calls=self._calls(process), reader=_READER).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.denied_reads == ()
