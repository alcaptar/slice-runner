from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.step import Step
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject, HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.local_activity_log import LocalActivityLog
from slice_runner.tests.activity_file import ActivityFile
from slice_runner.tests.doubles import (
    FixedInvocation,
    RecordedActivityLog,
    RecordedProcess,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
    StreamingProcess,
)
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.activity_log import ActivityLog
    from slice_runner.infrastructure.process import Process

_SUBJECT = HarnessCallSubject(coordinates=HarnessCallSpendMother.coordinates(), worktree="/repos/slice-runner")
_SLICE_ID = _SUBJECT.coordinates.slice_id.text


class Calling:
    @staticmethod
    def _runner(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        turns: RecordedTurnLog | None = None,
        activity: ActivityLog | None = None,
        spend_log: RecordedSpendLog | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> HarnessInvocationRunner:
        return HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=turns or RecordedTurnLog(),
                activity=activity or RecordedActivityLog(),
                spend_log=spend_log or RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )


class TestTheInvocationTravelsToTheProcess(Calling):
    def test_the_argv_the_text_and_the_cwd_of_the_invocation_reach_the_process(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        runner = self._runner(process)
        invocation = FixedInvocation(argv=["claude", "--model", "opus"], text="the prompt", cwd="/repos/slice-runner")

        runner.call(invocation, step=Step.VERIFY, subject=_SUBJECT)

        assert process.argv == invocation.argv
        assert process.stdin == invocation.text
        assert process.cwd == invocation.cwd


class TestWhatTheCallReturns(Calling):
    def test_the_envelope_returned_carries_the_structured_output_of_the_call(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        runner = self._runner(process)

        envelope = runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert envelope.structured_output == HarnessEnvelopeMother.recorded()["structured_output"]


class TestTheTraceOfTheCall(Calling):
    def test_the_session_the_slice_and_the_step_of_the_call_are_written_down(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.coordinates.slice_id.text, call.step, call.session) for call in trace.calls] == [
            (_SLICE_ID, Step.VERIFY, HarnessEnvelopeMother.SESSION_OF_THE_JUDGE)
        ]

    def test_the_trace_carries_the_repo_and_the_issue_of_the_subject(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.coordinates.repo, call.coordinates.issue) for call in trace.calls] == [
            (_SUBJECT.coordinates.repo, _SUBJECT.coordinates.issue)
        ]


class TestTheSpendLogOfTheCall(Calling):
    def test_the_session_and_what_it_spent_are_written_down(self) -> None:
        spend_log = RecordedSpendLog()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), spend_log=spend_log)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert spend_log.calls == [HarnessCallSpendMother.of_the_judge()]


class TestTheToolUseRecordingOfTheCall(Calling):
    def test_the_recorder_is_asked_for_the_slice_step_session_and_worktree_of_the_call(self) -> None:
        tool_uses = RecordedToolUseRecorder()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), tool_uses=tool_uses)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert [(call.slice_id, call.step, call.session, call.worktree) for call in tool_uses.calls] == [
            (_SLICE_ID, Step.VERIFY, HarnessEnvelopeMother.SESSION_OF_THE_JUDGE, _SUBJECT.worktree)
        ]


class TestTheTurnsObservedWhileTheCallIsInFlight(Calling):
    def test_every_tool_use_of_a_real_streamed_call_is_observed_labelled_with_the_step_it_was_called_with(self) -> None:
        turns = RecordedTurnLog()
        runner = self._runner(StreamingProcess(HarnessEnvelopeMother.streamed()), turns=turns)

        runner.call(FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT)

        assert [(turn.slice_id, turn.step, turn.number, turn.tool, turn.target) for turn in turns.turns] == [
            (_SLICE_ID, Step.IMPLEMENT, 1, "Write", "/private/tmp/stream-capture2/repo/hello.py"),
            (_SLICE_ID, Step.IMPLEMENT, 2, "StructuredOutput", None),
        ]


class TestTheStepNeverStaysFixedInsideTheCommonPiece(Calling):
    def test_two_calls_with_different_steps_each_produce_a_trace_carrying_its_own_step(self) -> None:
        trace = RecordedTrace()
        runner = self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), trace=trace)

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)
        runner.call(FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT)

        assert [call.step for call in trace.calls] == [Step.VERIFY, Step.IMPLEMENT]


class TestTheLiveActivityOfTheCall(Calling, WithTheDurableStoresOutOfTheRealHome):
    _STREAMED_WRITE = ("Write", "/private/tmp/stream-capture2/repo/hello.py")
    _STREAMED_STRUCTURED_OUTPUT = ("StructuredOutput", "")

    def _live(self) -> HarnessInvocationRunner:
        return self._runner(
            StreamingProcess(HarnessEnvelopeMother.streamed()), activity=LocalActivityLog(clock=self.frozen_at())
        )

    @pytest.mark.parametrize(
        ("step", "actor"), [(Step.IMPLEMENT, "implementer"), (Step.VERIFY, "judge")], ids=["implementer", "judge"]
    )
    def test_every_tool_use_of_the_call_is_a_line_labelled_with_who_called(
        self, tmp_path: Path, step: Step, actor: str
    ) -> None:
        self._live().call(FixedInvocation(), step=step, subject=_SUBJECT)

        assert ActivityFile.what_was_done(tmp_path, _SUBJECT.coordinates) == [
            (actor, *self._STREAMED_WRITE),
            (actor, *self._STREAMED_STRUCTURED_OUTPUT),
        ]

    def test_two_calls_of_the_same_run_leave_only_the_lines_of_the_second(self, tmp_path: Path) -> None:
        runner = self._live()
        runner.call(FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT)
        before = ActivityFile.lines_of(tmp_path, _SUBJECT.coordinates)
        assert len(before) == 2

        runner.call(FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT)

        assert {line["actor"] for line in ActivityFile.lines_of(tmp_path, _SUBJECT.coordinates)} == {"judge"}
        assert len(ActivityFile.lines_of(tmp_path, _SUBJECT.coordinates)) == 2

    def test_a_call_that_streams_nothing_still_empties_the_lines_of_the_previous_one(self, tmp_path: Path) -> None:
        activity = LocalActivityLog(clock=self.frozen_at())
        self._runner(StreamingProcess(HarnessEnvelopeMother.streamed()), activity=activity).call(
            FixedInvocation(), step=Step.IMPLEMENT, subject=_SUBJECT
        )

        self._runner(RecordedProcess(HarnessEnvelopeMother.recorded()), activity=activity).call(
            FixedInvocation(), step=Step.VERIFY, subject=_SUBJECT
        )

        assert ActivityFile.lines_of(tmp_path, _SUBJECT.coordinates) == []
