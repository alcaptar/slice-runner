from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closure import Closure
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.infrastructure.local_event_reader import LocalEventReader
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.entrypoint_process import WithTheEntrypointLaunchingNothing
from slice_runner.tests.mothers.child_issue_mother import ChildIssueMother
from slice_runner.tests.mothers.event_mother import EventMother

if TYPE_CHECKING:
    import pytest


class TestTheCommandThatRegistersThePendingSlices(WithTheDurableStoresOutOfTheRealHome):
    _SUB_ISSUES = (
        {"number": 524, "title": "HU-123 slice-01 (x): y", "state": "open"},
        {"number": 525, "title": "slice-02 (done): y", "state": "closed"},
    )

    @classmethod
    def _registered(cls, process: ScriptedProcess) -> int:
        return Cli(process=process, budgets=Budgets()).register(
            repo=ChildIssueMother.REPO,
            issue=ChildIssueMother.PARENT,
            reader=LocalEventReader(),
            log=LocalEventLog(),
            clock=cls.frozen_at(),
        )

    @staticmethod
    def _answering(entries: tuple[dict[str, object], ...]) -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(entries), stderr=""))

    @staticmethod
    def _ledger() -> DurableLedger[EventPayload]:
        return DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload)

    def test_it_writes_a_pending_row_for_the_open_subissue_with_the_canonical_id_of_its_title(self) -> None:
        code = self._registered(self._answering(self._SUB_ISSUES))

        events = LocalEventReader().read_since(EventCursor.start()).events
        assert code == ExitCode.OK
        assert [(event.repo, event.issue, event.slice_id, event.step, event.closure) for event in events] == [
            (ChildIssueMother.REPO, 524, "HU-123-01", None, Closure.open())
        ]

    def test_the_pending_row_in_the_ledger_has_the_pending_standing_and_no_step_key(self) -> None:
        self._registered(self._answering(self._SUB_ISSUES))

        (line,) = self._ledger().path().read_text(encoding="utf-8").splitlines()
        row = json.loads(line)
        assert row["standing"] == "pending"
        assert "step" not in row
        assert "status" not in row

    def test_registering_twice_writes_the_rows_only_once(self) -> None:
        self._registered(self._answering(self._SUB_ISSUES))

        self._registered(self._answering(self._SUB_ISSUES))

        assert len(LocalEventReader().read_since(EventCursor.start()).events) == 1

    def test_a_log_this_generation_did_not_write_exits_with_the_usage_error_of_follow_and_writes_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalEventLog().emit(EventMother.advancing())
        with self._ledger().path().open("a", encoding="utf-8") as stream:
            stream.write("not json\n")
        before = self._ledger().path().read_text(encoding="utf-8")
        process = self._answering(self._SUB_ISSUES)
        capsys.readouterr()

        code = self._registered(process)

        output = capsys.readouterr()
        assert code == ExitCode.USAGE_ERROR
        assert self._ledger().path().read_text(encoding="utf-8") == before
        assert output.out == ""
        assert "not JSON" in output.err
        assert process.calls == []

    def test_a_failing_gh_exits_as_an_interrupted_run_and_writes_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="gh: Not Found (HTTP 404)"))

        code = self._registered(process)

        assert code == ExitCode.RUN_INTERRUPTED
        assert "Not Found" in capsys.readouterr().err
        assert not self._ledger().path().exists()

    def test_a_title_without_the_slice_heading_exits_with_the_usage_error_and_writes_nothing(self) -> None:
        process = self._answering(({"number": 9, "title": "a plain issue", "state": "open"},))

        code = self._registered(process)

        assert code == ExitCode.USAGE_ERROR
        assert not self._ledger().path().exists()


class TestFollowingAPendingSlice(WithTheEntrypointLaunchingNothing, WithTheDurableStoresOutOfTheRealHome):
    def test_follow_prints_the_pending_row_with_no_step_the_standing_and_zero_spend(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalEventLog().emit(EventMother.pending())
        capsys.readouterr()

        code = Cli.main(["follow", "--once"])

        assert code == ExitCode.OK
        assert capsys.readouterr().out.splitlines() == [
            "2024-01-01T12:30:45+00:00 alcaptar/slice-runner #150 slice-05 - pending $0.00"
        ]

    def test_after_a_real_event_of_the_same_slice_follow_prints_a_single_line_for_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = LocalEventLog()
        log.emit(EventMother.pending())
        log.emit(EventMother.advancing_again(minutes_later=3))
        capsys.readouterr()

        Cli.main(["follow", "--once"])

        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 1
        assert "run-controls in-progress" in lines[0]
