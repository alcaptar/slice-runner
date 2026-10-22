from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure import local_event_log
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class ExpectedRow:
    ROUNDS: ClassVar[dict[str, object]] = {
        "controls": {"used": 0, "limit": 2},
        "hygiene": {"used": 0, "limit": 2},
        "judge": {"used": 0, "limit": 2},
        "ci": {"used": 0, "limit": 1},
        "ci_indeterminate": {"used": 0, "limit": 10},
        "catch_up": {"used": 0, "limit": 3},
    }
    ADVANCING: ClassVar[dict[str, object]] = {
        "slice_id": "slice-05",
        "repo": EventMother.REPO,
        "issue": EventMother.ISSUE,
        "standing": "in-progress",
        "step": "run-controls",
        "ts": "2024-01-01T12:30:45+00:00",
        "rounds": ROUNDS,
        "spend": {
            "cost_usd": 0.3433209,
            "turns": 9,
            "duration_ms": 36315,
            "calls": 1,
            "models": ["claude-sonnet-5"],
            "input_tokens": 13,
            "output_tokens": 1159,
            "cache_creation_tokens": 42251,
            "cache_read_tokens": 241303,
            "ttft_ms": 5588,
            "duration_api_ms": 32189,
        },
        "budget_usd": 50.0,
        "parent": FeatureSliceMother.PARENT,
        "name": FeatureSliceMother.NAME,
    }


class WrittenEvents:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "transitions.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestWhatIsWrittenDownOfAnEvent(WithTheDurableStoresOutOfTheRealHome):
    def test_an_event_is_written_with_the_coordinates_the_standing_the_step_the_rounds_the_spend_and_the_budget(
        self, tmp_path: Path
    ) -> None:
        LocalEventLog().emit(EventMother.advancing())

        assert WrittenEvents.records_under(tmp_path) == [ExpectedRow.ADVANCING]


class TestTheLogOnlyGrows(WithTheDurableStoresOutOfTheRealHome):
    def test_a_second_event_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        log = LocalEventLog()

        log.emit(EventMother.advancing())
        log.emit(EventMother.closed())

        assert len(WrittenEvents.records_under(tmp_path)) == 2


class TestTheSameEventStillReachesStandardError(WithTheDurableStoresOutOfTheRealHome):
    def test_the_event_reaches_standard_error_as_the_contract_payload_and_never_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalEventLog().emit(EventMother.advancing())

        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err) == ExpectedRow.ADVANCING

    def test_two_consecutive_events_land_on_two_separable_lines_and_never_on_a_single_run_together(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = LocalEventLog()

        log.emit(EventMother.advancing())
        log.emit(EventMother.closed())

        payloads = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
        assert [(payload["step"], payload["standing"]) for payload in payloads] == [
            ("run-controls", "in-progress"),
            ("await-merge", "merged"),
        ]


class TestWhereTheLogLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_event_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalEventLog().emit(EventMother.advancing())

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "transitions.jsonl").exists()

    def test_the_ledger_path_is_composed_under_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        events = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()

        assert events == tmp_path / "slice-runner" / "runs" / "transitions.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_emitting_an_event_reaches_only_the_events_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_event_log, monkeypatch)

        LocalEventLog().emit(EventMother.advancing())

        (events_stub,) = created
        assert (events_stub.name, events_stub.row) == (LocalEventLog.LEDGER, EventPayload)
        assert len(events_stub.appended) == 1
        assert not (tmp_path / "slice-runner").exists()
