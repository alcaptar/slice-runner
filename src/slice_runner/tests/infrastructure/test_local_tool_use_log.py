from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.step import Step
from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause
from slice_runner.infrastructure import local_tool_use_log
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.infrastructure.tool_use_log import UnrecordedCallToolUse
from slice_runner.infrastructure.tool_use_payload import CallToolUsePayload, UnrecordedCallToolUsePayload
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.harness_call_tool_use_mother import HarnessCallToolUseMother

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class WrittenToolUses:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "tool-uses.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestWhatIsWrittenDownOfACall(WithTheDurableStoresOutOfTheRealHome):
    def test_a_call_is_written_as_the_slice_the_step_the_session_and_every_tool_use_it_made(
        self, tmp_path: Path
    ) -> None:
        LocalToolUseLog(clock=self.frozen_at()).record(HarnessCallToolUseMother.of_the_implementer())

        assert WrittenToolUses.records_under(tmp_path) == [
            {
                "repo": HarnessCallToolUseMother.REPO,
                "issue": HarnessCallToolUseMother.ISSUE,
                "slice_id": HarnessCallToolUseMother.SLICE_ID,
                "step": "implement",
                "session": HarnessCallToolUseMother.SESSION,
                "ts": _STAMP.isoformat(),
                "uses": [
                    {"turn": 1, "tool": "Read", "path": "src/x.py"},
                    {"turn": 2, "tool": "Bash", "command": "make check"},
                ],
            }
        ]

    def test_a_long_command_is_written_whole_and_without_any_mark_of_having_been_cut(self, tmp_path: Path) -> None:
        LocalToolUseLog(clock=self.frozen_at()).record(
            HarnessCallToolUseMother.of_the_implementer_with_a_long_command()
        )

        assert WrittenToolUses.records_under(tmp_path)[0]["uses"] == [
            {"turn": 1, "tool": "Bash", "command": HarnessCallToolUseMother.LONG_COMMAND}
        ]

    def test_a_row_written_before_commands_were_recorded_is_still_read_back(self) -> None:
        row = {
            "ts": _STAMP.isoformat(),
            "repo": HarnessCallToolUseMother.REPO,
            "issue": HarnessCallToolUseMother.ISSUE,
            "slice_id": HarnessCallToolUseMother.SLICE_ID,
            "step": "implement",
            "session": HarnessCallToolUseMother.SESSION,
            "uses": [{"turn": 1, "tool": "Read", "path": "src/x.py"}, {"turn": 2, "tool": "Bash"}],
        }

        assert CallToolUsePayload.model_validate(row).uses[1].command is None


class TestARowOfTheRetiredUnderstandStep:
    def test_a_row_written_when_the_run_still_understood_is_read_back_as_the_understand_step(self) -> None:
        row = {
            "ts": _STAMP.isoformat(),
            "repo": HarnessCallToolUseMother.REPO,
            "issue": HarnessCallToolUseMother.ISSUE,
            "slice_id": HarnessCallToolUseMother.SLICE_ID,
            "step": "understand",
            "session": HarnessCallToolUseMother.SESSION,
            "uses": [{"turn": 1, "tool": "Read", "path": "src/x.py"}],
        }

        assert CallToolUsePayload.model_validate(row).step is Step.UNDERSTAND


class TestTheLogOnlyGrows(WithTheDurableStoresOutOfTheRealHome):
    def test_a_second_call_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        log = LocalToolUseLog(clock=self.frozen_at())

        log.record(HarnessCallToolUseMother.of_the_implementer())
        log.record(HarnessCallToolUseMother.of_the_implementer())

        assert len(WrittenToolUses.records_under(tmp_path)) == 2


class TestWhereTheLogLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(
            HarnessCallToolUseMother.of_the_implementer()
        )

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "tool-uses.jsonl").exists()

    def test_the_ledger_paths_are_composed_under_runs_and_not_under_the_retired_trace_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        uses = DurableLedger(name=LocalToolUseLog.LEDGER, row=CallToolUsePayload).path()
        unrecorded = DurableLedger(name=LocalToolUseLog.UNRECORDED_LEDGER, row=UnrecordedCallToolUsePayload).path()

        assert uses == tmp_path / "slice-runner" / "runs" / "tool-uses.jsonl"
        assert unrecorded == tmp_path / "slice-runner" / "runs" / "unrecorded-tool-uses.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_recording_a_call_reaches_only_the_uses_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_tool_use_log, monkeypatch)

        LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(
            HarnessCallToolUseMother.of_the_implementer()
        )

        uses_stub, unrecorded_stub = created
        assert (uses_stub.name, uses_stub.row) == (LocalToolUseLog.LEDGER, CallToolUsePayload)
        assert (unrecorded_stub.name, unrecorded_stub.row) == (
            LocalToolUseLog.UNRECORDED_LEDGER,
            UnrecordedCallToolUsePayload,
        )
        assert len(uses_stub.appended) == 1
        assert unrecorded_stub.appended == []
        assert not (tmp_path / "slice-runner").exists()

    def test_recording_an_unrecorded_call_reaches_only_the_unrecorded_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_tool_use_log, monkeypatch)

        LocalToolUseLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record_unrecorded(
            UnrecordedCallToolUse(
                coordinates=HarnessCallToolUseMother.coordinates(),
                step=Step.IMPLEMENT,
                session="never-recorded",
                cause=UnrecordedConversationCause.NOT_FOUND,
            )
        )

        uses_stub, unrecorded_stub = created
        assert uses_stub.appended == []
        assert len(unrecorded_stub.appended) == 1
        assert not (tmp_path / "slice-runner").exists()
