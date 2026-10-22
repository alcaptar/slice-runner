from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.clock import Clock
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_reader import EventBatch
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.follow_activity_v2_payload import FollowActivityV2Payload
from slice_runner.infrastructure.local_activity_log import LocalActivityLog
from slice_runner.infrastructure.local_activity_reader import LocalActivityReader
from slice_runner.tests.doubles import ProcessDoubles, ScriptedEventReader
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.activity_mother import ActivityMother
from slice_runner.tests.mothers.event_mother import EventMother

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

_COORDINATES = ActivityMother.coordinates_of_the_followed_slice()
_STAMP_MILLISECONDS = 1786363200000


class TestFollowingTheLiveActivityAsJson(WithTheDurableStoresOutOfTheRealHome):
    def _log(self) -> LocalActivityLog:
        return LocalActivityLog(clock=self.frozen_at())

    @staticmethod
    def _cli() -> Cli:
        return Cli(process=ProcessDoubles.exiting(), budgets=Budgets(), activity=LocalActivityReader())

    @staticmethod
    def _printed_activity(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
        lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

        return [line for line in lines if line["kind"] == "activity"]

    @staticmethod
    def _clock_that_runs(between_reads: Callable[[], None]) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)

        def sleep(*, seconds: int) -> None:
            if clock.sleep.call_count > 1:
                raise KeyboardInterrupt
            between_reads()

        clock.sleep.side_effect = sleep

        return clock

    @staticmethod
    def _events() -> ScriptedEventReader:
        return ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(), cursor=EventCursor(offset=10)),
        )

    def test_every_line_of_the_file_is_printed_as_an_activity_line_of_the_contract_v2(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = self._log()
        log.record(ActivityMother.in_the_followed_slice(tool="Edit", target="a.py"))
        log.record(ActivityMother.in_the_followed_slice(tool="Read", target="b.py"))

        code = self._cli().follow(
            repo=None,
            once=True,
            as_json=True,
            reader=self._events(),
            clock=self._clock_that_runs(lambda: None),
        )

        printed = self._printed_activity(capsys)
        assert code == ExitCode.OK
        assert [(line["tool"], line["target"], line["ts"]) for line in printed] == [
            ("Edit", "a.py", _STAMP_MILLISECONDS),
            ("Read", "b.py", _STAMP_MILLISECONDS),
        ]
        assert [FollowActivityV2Payload.from_contract(line).to_contract() for line in printed] == printed

    def test_a_line_written_while_following_is_printed_once_after_the_ones_already_seen(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = self._log()
        log.record(ActivityMother.in_the_followed_slice(tool="Edit", target="a.py"))

        def write_one_more() -> None:
            log.record(ActivityMother.in_the_followed_slice(tool="Read", target="b.py"))

        self._cli().follow(
            repo=None,
            once=False,
            as_json=True,
            reader=self._events(),
            clock=self._clock_that_runs(write_one_more),
        )

        assert [line["tool"] for line in self._printed_activity(capsys)] == ["Edit", "Read"]

    def test_the_lines_written_after_the_file_was_emptied_between_two_reads_are_printed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = self._log()
        log.record(ActivityMother.in_the_followed_slice(tool="Edit", target="a.py"))
        log.record(ActivityMother.in_the_followed_slice(tool="Edit", target="b.py"))

        def empty_and_write_a_new_one() -> None:
            log.restart(_COORDINATES)
            log.record(ActivityMother.in_the_followed_slice(tool="Bash", target="c"))

        self._cli().follow(
            repo=None,
            once=False,
            as_json=True,
            reader=self._events(),
            clock=self._clock_that_runs(empty_and_write_a_new_one),
        )

        printed = self._printed_activity(capsys)
        assert [line["target"] for line in printed] == ["a.py", "b.py", "c"]
        assert [FollowActivityV2Payload.from_contract(line).to_contract() for line in printed] == printed

    def test_the_text_report_prints_no_activity_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._log().record(ActivityMother.in_the_followed_slice(tool="Edit", target="a.py"))

        self._cli().follow(
            repo=None,
            once=True,
            reader=self._events(),
            clock=self._clock_that_runs(lambda: None),
        )

        assert "Edit" not in capsys.readouterr().out
