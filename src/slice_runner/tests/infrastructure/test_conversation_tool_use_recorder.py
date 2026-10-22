from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.conversation_tool_use_recorder import ConversationToolUseRecorder
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject, HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.local_conversation_log import LocalConversationLog
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.tests.doubles import (
    RecordedActivityLog,
    RecordedProcess,
    RecordedSourceReader,
    RecordedSpendLog,
    RecordedTrace,
    RecordedTurnLog,
)
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.conversation_transcript_mother import ConversationTranscriptMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

if TYPE_CHECKING:
    from pathlib import Path

_WORKTREE = ConversationTranscriptMother.WORKTREE
_REPO = "alcaptar/slice-runner"
_ISSUE = 45
_SLICE_ID = "slice-05"
_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP
_SUBJECT = HarnessCallSubject(
    coordinates=SliceCoordinates(repo=_REPO, issue=_ISSUE, slice_id=CanonicalSliceId.of_text(_SLICE_ID)),
    worktree=_WORKTREE,
)


class WrittenToolUses:
    LEDGER: tuple[str, ...] = ("slice-runner", "runs", "tool-uses.jsonl")

    @classmethod
    def records_under(cls, root: Path) -> list[dict[str, object]]:
        ledger = root.joinpath(*cls.LEDGER)
        if not ledger.exists():
            return []

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestARecordedConversation(WithTheDurableStoresOutOfTheRealHome):
    def test_every_tool_use_of_the_conversation_lands_in_the_log_labelled_with_the_slice_step_and_session(
        self, tmp_path: Path
    ) -> None:
        ConversationTranscriptMother.written_under(tmp_path)
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.IMPLEMENT, session=ConversationTranscriptMother.SESSION)

        assert WrittenToolUses.records_under(tmp_path) == [
            {
                "repo": _REPO,
                "issue": _ISSUE,
                "slice_id": _SLICE_ID,
                "step": "implement",
                "session": ConversationTranscriptMother.SESSION,
                "ts": _STAMP.isoformat(),
                "uses": [
                    {
                        "turn": 2,
                        "tool": "Bash",
                        "command": (
                            "uv run pytest src/slice_runner/tests/infrastructure/test_local_process.py"
                            " -x -q 2>&1 | tail -40"
                        ),
                    },
                    {
                        "turn": 4,
                        "tool": "Bash",
                        "command": (
                            'grep -n "process_timeout_seconds"'
                            " /Users/someone/repos/worktree1/src/slice_runner/domain/budgets.py"
                        ),
                    },
                ],
            }
        ]

    def test_a_call_the_harness_refused_lands_marked_so_a_fight_can_be_counted_without_reading_the_transcript(
        self, tmp_path: Path
    ) -> None:
        ConversationTranscriptMother.written_under(
            tmp_path, recorded=ConversationTranscriptMother.REJECTED_STRUCTURED_OUTPUT
        )
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.UNDERSTAND, session=ConversationTranscriptMother.SESSION)

        assert WrittenToolUses.records_under(tmp_path)[0]["uses"] == [
            {"turn": 1, "tool": "StructuredOutput", "failed": True}
        ]


class WrittenUnrecordedToolUses:
    LEDGER: tuple[str, ...] = ("slice-runner", "runs", "unrecorded-tool-uses.jsonl")

    @classmethod
    def records_under(cls, root: Path) -> list[dict[str, object]]:
        ledger = root.joinpath(*cls.LEDGER)
        if not ledger.exists():
            return []

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestATranscriptThatCannotBeRead(WithTheDurableStoresOutOfTheRealHome):
    def test_a_session_never_recorded_leaves_the_run_going_instead_of_raising(self, tmp_path: Path) -> None:
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.IMPLEMENT, session="never-recorded")

        assert WrittenToolUses.records_under(tmp_path) == []

    def test_a_session_never_recorded_is_not_abandoned_in_silence_but_says_so(self, tmp_path: Path) -> None:
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.IMPLEMENT, session="never-recorded")

        assert WrittenUnrecordedToolUses.records_under(tmp_path) == [
            {
                "repo": _REPO,
                "issue": _ISSUE,
                "slice_id": _SLICE_ID,
                "step": "implement",
                "session": "never-recorded",
                "ts": _STAMP.isoformat(),
                "cause": "not-found",
            }
        ]

    def test_a_corrupted_transcript_leaves_the_run_going_instead_of_raising(self, tmp_path: Path) -> None:
        session = "broken-session"
        ConversationTranscriptMother.destination_of(tmp_path, session=session).write_text(
            "not json at all\n", encoding="utf-8"
        )
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.IMPLEMENT, session=session)

        assert WrittenToolUses.records_under(tmp_path) == []

    def test_a_corrupted_transcript_is_not_abandoned_in_silence_but_says_a_different_cause(
        self, tmp_path: Path
    ) -> None:
        session = "broken-session"
        ConversationTranscriptMother.destination_of(tmp_path, session=session).write_text(
            "not json at all\n", encoding="utf-8"
        )
        recorder = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )

        recorder.record_after(_SUBJECT, step=Step.IMPLEMENT, session=session)

        assert WrittenUnrecordedToolUses.records_under(tmp_path) == [
            {
                "repo": _REPO,
                "issue": _ISSUE,
                "slice_id": _SLICE_ID,
                "step": "implement",
                "session": session,
                "ts": _STAMP.isoformat(),
                "cause": "unreadable",
            }
        ]


class TestARunThatCallsBothStepsOfTheHarness(WithTheDurableStoresOutOfTheRealHome):
    _WORKTREE = ConversationTranscriptMother.WORKTREE
    _SESSION = ConversationTranscriptMother.SESSION

    @classmethod
    def _envelope(cls, structured_output: dict[str, object]) -> dict[str, object]:
        return HarnessEnvelopeMother.carrying(structured_output, recorded="implementer-two-paths") | {
            "session_id": cls._SESSION
        }

    @staticmethod
    def _calls(process: RecordedProcess, *, telemetry: HarnessTelemetry) -> HarnessInvocationRunner:
        return HarnessInvocationRunner(process=process, telemetry=telemetry)

    @classmethod
    def _run_both(cls, tmp_path: Path) -> None:
        ConversationTranscriptMother.written_under(tmp_path)
        tool_uses = ConversationToolUseRecorder(
            conversations=LocalConversationLog(),
            tool_use_log=LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()),
        )
        telemetry = HarnessTelemetry(
            trace=RecordedTrace(),
            turns=RecordedTurnLog(),
            activity=RecordedActivityLog(),
            spend_log=RecordedSpendLog(),
            tool_uses=tool_uses,
        )
        reader = RecordedSourceReader()

        ClaudeImplementer(
            calls=cls._calls(
                RecordedProcess(HarnessEnvelopeMother.recorded("implementer-two-paths") | {"session_id": cls._SESSION}),
                telemetry=telemetry,
            ),
            reader=reader,
        ).implement(replace(AssignmentMother.of_the_first_round(), worktree=cls._WORKTREE))
        ClaudeVerifier(
            calls=cls._calls(RecordedProcess(cls._envelope(JudgeVerdictMother.passing())), telemetry=telemetry),
            reader=reader,
        ).verify(JudgeMother.adversarial(), replace(SliceUnderReviewMother.of_the_slice(), worktree=cls._WORKTREE))

    def test_the_two_calls_each_leave_their_own_row_in_the_tool_use_ledger(self, tmp_path: Path) -> None:
        self._run_both(tmp_path)

        assert [(row["step"], row["session"]) for row in WrittenToolUses.records_under(tmp_path)] == [
            ("implement", self._SESSION),
            ("verify", self._SESSION),
        ]

    def test_none_of_the_two_calls_falls_back_to_the_unrecorded_ledger(self, tmp_path: Path) -> None:
        self._run_both(tmp_path)

        assert WrittenUnrecordedToolUses.records_under(tmp_path) == []
