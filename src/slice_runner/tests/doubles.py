from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, NoReturn
from unittest.mock import Mock, create_autospec

from slice_runner.domain.activity_log import ActivityLog
from slice_runner.domain.activity_reader import ActivityBatch, ActivityReader
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.cited_source import CitedSource
from slice_runner.domain.clock import Clock
from slice_runner.domain.corpus import Corpus, JudgedRound
from slice_runner.domain.debt_ledger import DebtDeclaration, DebtLedger
from slice_runner.domain.event_reader import EventBatch, EventReader
from slice_runner.domain.exceptions import UnreadableSourceError
from slice_runner.domain.gh_retry_policy import GhRetryPolicy
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.source_reader import SourceReader
from slice_runner.infrastructure.gh_call import GhCall
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocation
from slice_runner.infrastructure.process import (
    Process,
    ProcessOutput,
    ProcessTimedOutError,
)
from slice_runner.infrastructure.process_replacement import ExecutableNotFoundError, ProcessReplacement
from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder
from slice_runner.infrastructure.turn_log import TurnLog

if TYPE_CHECKING:
    from collections.abc import Callable

    from slice_runner.domain.activity import Activity
    from slice_runner.domain.call_spend_log import HarnessCallSpend
    from slice_runner.domain.call_trace import HarnessCall
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.debt_entry import DebtEntry
    from slice_runner.domain.design import Design
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.event_cursor import EventCursor
    from slice_runner.domain.slice_coordinates import SliceCoordinates
    from slice_runner.domain.source import Source
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject
    from slice_runner.infrastructure.turn_log import HarnessTurn


class ProcessDoubles:
    @staticmethod
    def exiting(*, code: int = 0, stdout: str = "", stderr: str = "") -> Mock:
        process: Mock = create_autospec(Process, spec_set=True, instance=True)
        process.run.return_value = ProcessOutput(code=code, stdout=stdout, stderr=stderr)
        return process


class RecordedProcess(Process):
    def __init__(self, output: dict[str, object], *, code: int = 0) -> None:
        self._output = output
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.cwd: str | None = None
        self.calls = 0

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.cwd = cwd
        self.calls += 1

        return ProcessOutput(code=self._code, stdout=json.dumps(self._output), stderr="")


class StreamingProcess(Process):
    def __init__(self, stdout: str, *, code: int = 0) -> None:
        self._stdout = stdout
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.cwd: str | None = None

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.cwd = cwd
        if on_line is not None:
            for line in self._stdout.splitlines():
                if line.strip():
                    on_line(line)

        return ProcessOutput(code=self._code, stdout=self._stdout, stderr="")


class TimingOutProcess(Process):
    CAP_SECONDS: ClassVar[int] = 1

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        raise ProcessTimedOutError(f"{argv[0]}: killed after {self.CAP_SECONDS}s")


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordedCall:
    argv: list[str] = field(default_factory=list)
    stdin: str = ""


class ScriptedProcess(Process):
    def __init__(self, *outputs: ProcessOutput) -> None:
        self._outputs = list(outputs)
        self.calls: list[RecordedCall] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))

        return self._outputs.pop(0)


@dataclass(frozen=True, kw_only=True, slots=True)
class Answer:
    to: tuple[str, ...]
    stdout: str = ""
    code: int = 0
    stderr: str = ""
    exact: bool = False

    @classmethod
    def to_exactly(cls, *argv: str, stdout: str = "", code: int = 0, stderr: str = "") -> Answer:
        return cls(to=argv, stdout=stdout, code=code, stderr=stderr, exact=True)

    def answers(self, argv: list[str]) -> bool:
        if self.exact:
            return list(self.to) == argv

        return all(token in argv for token in self.to)

    @property
    def output(self) -> ProcessOutput:
        return ProcessOutput(code=self.code, stdout=self.stdout, stderr=self.stderr)


class AnsweringByArgv(Process):
    def __init__(self, *answers: Answer) -> None:
        self._answers = answers
        self._given: set[int] = set()
        self.calls: list[RecordedCall] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))
        for position, answer in enumerate(self._answers):
            if position not in self._given and answer.answers(argv):
                if answer.exact:
                    self._given.add(position)

                return answer.output

        raise AssertionError(f"no answer was scripted for `{' '.join(argv)}`")

    @property
    def scripted(self) -> tuple[Answer, ...]:
        return self._answers

    def invoked(self, *tokens: str) -> bool:
        return any(all(token in call.argv for token in tokens) for call in self.calls)

    def times_invoked(self, *tokens: str) -> int:
        return sum(1 for call in self.calls if all(token in call.argv for token in tokens))

    def ran(self, *argv: str) -> bool:
        return list(argv) in [call.argv for call in self.calls]


class AnsweringByArgvWithADiffThatMoves(AnsweringByArgv):
    def __init__(self, *answers: Answer, diffs: tuple[str, ...]) -> None:
        super().__init__(*answers)
        self._diffs = diffs
        self._reads = 0

    @classmethod
    def over(cls, process: AnsweringByArgv, *, diffs: tuple[str, ...]) -> AnsweringByArgvWithADiffThatMoves:
        return cls(*process.scripted, diffs=diffs)

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        if not self._reads_the_text_of_the_diff(argv):
            return super().run(argv, stdin=stdin, cwd=cwd, on_line=on_line)

        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))
        text = self._diffs[min(self._reads, len(self._diffs) - 1)]
        self._reads += 1

        return ProcessOutput(code=0, stdout=text, stderr="")

    @staticmethod
    def _reads_the_text_of_the_diff(argv: list[str]) -> bool:
        return "diff" in argv and "--cached" in argv and "--name-only" not in argv and "--numstat" not in argv


class AnsweringByArgvRaisingOn(AnsweringByArgv):
    def __init__(self, *answers: Answer, when: tuple[str, ...], raises: Exception) -> None:
        super().__init__(*answers)
        self._when = when
        self._raises = raises

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        if all(token in argv for token in self._when):
            raise self._raises

        return super().run(argv, stdin=stdin, cwd=cwd, on_line=on_line)


class FixedInvocation(HarnessInvocation):
    def __init__(self, *, argv: list[str] | None = None, text: str = "prompt", cwd: str = "/repo") -> None:
        self._argv = argv if argv is not None else ["claude"]
        self._text = text
        self._cwd = cwd

    @property
    def argv(self) -> list[str]:
        return self._argv

    @property
    def text(self) -> str:
        return self._text

    @property
    def cwd(self) -> str:
        return self._cwd


class RecordedTrace(CallTrace):
    def __init__(self) -> None:
        self.calls: list[HarnessCall] = []

    def record(self, call: HarnessCall) -> None:
        self.calls.append(call)

    def sessions_of(self, *, repo: str, issue: int, slice_id: str, step: Step) -> tuple[str, ...]:
        return tuple(
            call.session
            for call in self.calls
            if call.coordinates.repo == repo
            and call.coordinates.issue == issue
            and call.coordinates.slice_id.text == slice_id
            and call.step == step
        )

    def calls_of(self, *, repo: str, issue: int, slice_id: str) -> tuple[HarnessCall, ...]:
        return tuple(
            call
            for call in self.calls
            if call.coordinates.repo == repo
            and call.coordinates.issue == issue
            and call.coordinates.slice_id.text == slice_id
        )


class RecordedTurnLog(TurnLog):
    def __init__(self) -> None:
        self.turns: list[HarnessTurn] = []

    def observe(self, turn: HarnessTurn) -> None:
        self.turns.append(turn)


class RecordedActivityLog(ActivityLog):
    def __init__(self) -> None:
        self.activities: list[Activity] = []
        self.restarts: list[SliceCoordinates] = []

    def restart(self, coordinates: SliceCoordinates) -> None:
        self.restarts.append(coordinates)

    def record(self, activity: Activity) -> None:
        self.activities.append(activity)


class RecordedSpendLog(CallSpendLog):
    def __init__(self) -> None:
        self.calls: list[HarnessCallSpend] = []

    def record(self, call: HarnessCallSpend) -> None:
        self.calls.append(call)

    def spend_of(self, sessions: tuple[str, ...]) -> HarnessSpend:
        return HarnessSpend.summing(call.spend for call in self.calls if call.session in sessions)

    def spend_of_the_slice(self, coordinates: SliceCoordinates) -> HarnessSpend:
        return HarnessSpend.summing(
            call.spend
            for call in self.calls
            if call.coordinates.repo == coordinates.repo
            and call.coordinates.issue == coordinates.issue
            and call.coordinates.slice_id.text == coordinates.slice_id.text
        )


class RecordedCorpus(Corpus):
    def __init__(self) -> None:
        self.entries: list[CorpusEntry] = []

    def record(self, entry: CorpusEntry) -> None:
        self.entries.append(entry)

    def size_of_the_last_verification(self, coordinates: SliceCoordinates) -> DiffStats | None:
        matching = [entry for entry in self.entries if self._matches(entry, coordinates)]

        return matching[-1].diff.stats if matching else None

    def fingerprint_of_the_last_verification(self, coordinates: SliceCoordinates) -> str | None:
        matching = [entry for entry in self.entries if self._matches(entry, coordinates)]

        return matching[-1].diff.fingerprint if matching else None

    def rounds_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[JudgedRound, ...]:
        last_of: dict[int, CorpusEntry] = {}
        for entry in self.entries:
            if self._matches(entry, coordinates):
                last_of[entry.verify_round] = entry

        return tuple(
            JudgedRound(round=verify_round, findings=entry.verdict.findings)
            for verify_round, entry in sorted(last_of.items())
        )

    @staticmethod
    def _matches(entry: CorpusEntry, coordinates: SliceCoordinates) -> bool:
        return (
            entry.repo == coordinates.repo
            and entry.issue == coordinates.issue
            and entry.slice_id == coordinates.slice_id.text
        )


class RecordedDebtLedger(DebtLedger):
    def __init__(self) -> None:
        self.entries: list[DebtEntry] = []

    def record(self, entry: DebtEntry) -> None:
        self.entries.append(entry)

    def declarations_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[DebtDeclaration, ...]:
        return tuple(
            DebtDeclaration(left_out=entry.left_out) for entry in self.entries if self._matches(entry, coordinates)
        )

    @staticmethod
    def _matches(entry: DebtEntry, coordinates: SliceCoordinates) -> bool:
        return entry.coordinates == coordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordedToolUseCall:
    slice_id: str
    step: Step
    session: str
    worktree: str


class RecordedToolUseRecorder(ToolUseRecorder):
    def __init__(self) -> None:
        self.calls: list[RecordedToolUseCall] = []

    def record_after(self, subject: HarnessCallSubject, *, step: Step, session: str) -> None:
        self.calls.append(
            RecordedToolUseCall(
                slice_id=subject.coordinates.slice_id.text, step=step, session=session, worktree=subject.worktree
            )
        )


class RecordingClock(Clock):
    def __init__(self) -> None:
        self.slept_seconds: list[int] = []

    def sleep(self, *, seconds: int) -> None:
        self.slept_seconds.append(seconds)

    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class RecordedSourceReader(SourceReader):
    DEFAULT_CONTENT: ClassVar[str] = "reglas del repo"

    def __init__(self, *, contents: dict[str, str] | None = None, unreadable: frozenset[str] = frozenset()) -> None:
        self._contents = contents or {}
        self._unreadable = unreadable
        self.calls: list[tuple[str, Source]] = []

    def read_all(
        self, *, worktree: str, sources: tuple[Source, ...], designs: tuple[Design, ...] = ()
    ) -> tuple[CitedSource, ...]:
        cited = []
        for source in sources:
            self.calls.append((worktree, source))
            if source.path in self._unreadable:
                raise UnreadableSourceError(f"{source.path} was scripted as unreadable for this test")

            cited.append(CitedSource(source=source, content=self._contents.get(source.path, self.DEFAULT_CONTENT)))

        return tuple(cited)


class GhCallDoubles:
    @staticmethod
    def wired(process: Process, *, budgets: Budgets | None = None, clock: Clock | None = None) -> GhCall:
        return GhCall(
            process=process, policy=GhRetryPolicy(budgets=budgets or Budgets()), clock=clock or RecordingClock()
        )


class ScriptedEventReader(EventReader):
    def __init__(self, *batches: EventBatch) -> None:
        self._batches = list(batches)
        self.cursors: list[EventCursor] = []

    def read_since(self, cursor: EventCursor) -> EventBatch:
        self.cursors.append(cursor)

        return self._batches.pop(0)


class RecordedActivityReader(ActivityReader):
    def __init__(self, batches: dict[SliceCoordinates, ActivityBatch]) -> None:
        self._batches = batches
        self.reads: list[tuple[SliceCoordinates, EventCursor]] = []

    def read_since(self, coordinates: SliceCoordinates, cursor: EventCursor) -> ActivityBatch:
        self.reads.append((coordinates, cursor))

        return self._batches.get(coordinates, ActivityBatch(activities=(), cursor=cursor))


class ReplacementRequestedError(Exception):
    pass


class RecordedReplacement(ProcessReplacement):
    def __init__(self) -> None:
        self.argvs: list[list[str]] = []

    def replaced_by(self, argv: list[str]) -> NoReturn:
        self.argvs.append(list(argv))

        raise ReplacementRequestedError


class MissingExecutableReplacement(ProcessReplacement):
    def replaced_by(self, argv: list[str]) -> NoReturn:
        raise ExecutableNotFoundError(f"{argv[0]} was scripted as missing for this test")
