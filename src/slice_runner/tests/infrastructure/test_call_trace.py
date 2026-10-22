from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.domain.step import Step
from slice_runner.infrastructure import local_call_trace
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.infrastructure.retired_ledger_directory import RetiredLedgerDirectory
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(autouse=True)
def _forbid_opening_the_retired_log_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    real_open: Callable[..., object] = io.open

    def guarded(file: object, *args: object, **kwargs: object) -> object:
        if isinstance(file, str | os.PathLike) and Path(str(file)).parts[-3:-1] == RetiredLedgerDirectory.SEGMENTS:
            raise AssertionError(f"the retired log directory must never be opened: {file!r}")

        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", guarded)
    monkeypatch.setattr("builtins.open", guarded)


_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class WrittenTrace:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "calls.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestWhatIsWrittenDownOfACall(WithTheDurableStoresOutOfTheRealHome):
    def test_a_call_is_written_as_the_run_it_came_from_the_step_it_served_and_the_session_of_its_conversation(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace(clock=self.frozen_at()).record(HarnessCallMother.of_the_implementer())

        assert WrittenTrace.records_under(tmp_path) == [
            {
                "repo": HarnessCallMother.REPO,
                "issue": HarnessCallMother.ISSUE,
                "slice_id": HarnessCallMother.SLICE_ID,
                "step": "implement",
                "session": HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,
                "ts": _STAMP.isoformat(),
            }
        ]


class TestTheTraceOnlyGrows(WithTheDurableStoresOutOfTheRealHome):
    def test_the_two_calls_of_a_slice_are_both_kept_so_the_judge_does_not_overwrite_the_implementer(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())

        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())

        assert [(record["step"], record["session"]) for record in WrittenTrace.records_under(tmp_path)] == [
            ("implement", HarnessCallMother.SESSION_OF_THE_IMPLEMENTER),
            ("verify", HarnessCallMother.SESSION_OF_THE_JUDGE),
        ]


class TestFindingTheSessionOfAPastCall(WithTheDurableStoresOutOfTheRealHome):
    def test_the_session_of_the_call_that_served_that_run_and_step_is_returned(self, tmp_path: Path) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,)

    def test_every_matching_call_is_returned_in_the_order_it_was_recorded_so_the_latest_retry_is_last(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, HarnessCallMother.SESSION_OF_THE_IMPLEMENTER)

    def test_a_slice_and_step_never_recorded_returns_nothing_instead_of_guessing_a_session(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace(clock=self.frozen_at()).record(HarnessCallMother.of_the_implementer())

        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id="slice-99", step=Step.VERIFY
        )

        assert found == ()

    def test_a_trace_never_written_returns_nothing_instead_of_failing(self, tmp_path: Path) -> None:
        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == ()

    def test_two_features_that_happen_to_share_a_slice_id_are_told_apart_by_their_repo_and_issue(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        other_feature = HarnessCallMother.of_the_implementer_of_another_feature()
        trace.record(other_feature)

        found = trace.sessions_of(
            repo=HarnessCallMother.OTHER_REPO,
            issue=HarnessCallMother.OTHER_ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (other_feature.session,)

    def test_a_line_from_before_this_run_carried_identity_is_rejected_instead_of_matched_by_accident(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            json.dumps({"slice_id": HarnessCallMother.SLICE_ID, "step": "implement", "session": "old-session"}) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace(clock=self.frozen_at()).sessions_of(
                repo=HarnessCallMother.REPO,
                issue=HarnessCallMother.ISSUE,
                slice_id=HarnessCallMother.SLICE_ID,
                step=Step.IMPLEMENT,
            )

    def test_a_call_recorded_with_a_slice_identifier_carrying_a_user_story_is_found_by_that_identifier(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer_of_a_slice_with_a_user_story())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID_WITH_A_USER_STORY,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,)

    def test_a_line_written_by_the_old_bare_identifier_does_not_match_the_new_prefixed_one(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            json.dumps(
                {
                    "ts": _STAMP.isoformat(),
                    "repo": HarnessCallMother.REPO,
                    "issue": HarnessCallMother.ISSUE,
                    "slice_id": "slice-05",
                    "step": "implement",
                    "session": "old-session",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        found_by_the_old_bare_identifier = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id="slice-05", step=Step.IMPLEMENT
        )
        found_by_the_new_prefixed_identifier = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id="PROJ-1234-05",
            step=Step.IMPLEMENT,
        )

        assert found_by_the_old_bare_identifier == ("old-session",)
        assert found_by_the_new_prefixed_identifier == ()

    def test_a_line_that_is_not_json_is_refused_instead_of_being_skipped_in_silence(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("not json\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace(clock=self.frozen_at()).sessions_of(
                repo=HarnessCallMother.REPO,
                issue=HarnessCallMother.ISSUE,
                slice_id=HarnessCallMother.SLICE_ID,
                step=Step.IMPLEMENT,
            )

    def test_a_line_this_program_did_not_write_is_refused_instead_of_being_skipped_in_silence(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"step": "implement"}) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace(clock=self.frozen_at()).sessions_of(
                repo=HarnessCallMother.REPO,
                issue=HarnessCallMother.ISSUE,
                slice_id=HarnessCallMother.SLICE_ID,
                step=Step.IMPLEMENT,
            )


class TestAnEarlierGenerationInTheSameLedger(WithTheDurableStoresOutOfTheRealHome):
    def test_a_line_of_another_slice_that_this_generation_cannot_read_does_not_block_finding_ours(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        earlier = {"session": "older-session", "step": str(Step.IMPLEMENT), "repo": "org/other", "issue": 7}
        ledger.write_text(json.dumps(earlier) + "\n", encoding="utf-8")
        trace = LocalCallTrace(clock=self.frozen_at())
        mine = HarnessCallMother.of_the_implementer()
        trace.record(mine)

        found = trace.sessions_of(
            repo=mine.coordinates.repo,
            issue=mine.coordinates.issue,
            slice_id=mine.coordinates.slice_id.text,
            step=mine.step,
        )

        assert found == (mine.session,)


class TestFindingTheCallsOfAPastSlice(WithTheDurableStoresOutOfTheRealHome):
    def test_every_call_of_the_slice_across_every_step_is_returned_in_the_order_it_was_recorded(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())

        found = trace.calls_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert [(call.step, call.session) for call in found] == [
            (Step.IMPLEMENT, HarnessCallMother.SESSION_OF_THE_IMPLEMENTER),
            (Step.VERIFY, HarnessCallMother.SESSION_OF_THE_JUDGE),
        ]

    def test_a_call_recorded_with_a_slice_identifier_carrying_a_user_story_is_found_by_that_identifier(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer_of_a_slice_with_a_user_story())

        found = trace.calls_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID_WITH_A_USER_STORY,
        )

        assert [call.session for call in found] == [HarnessCallMother.SESSION_OF_THE_IMPLEMENTER]

    def test_a_slice_never_recorded_returns_nothing_instead_of_guessing_a_call(self, tmp_path: Path) -> None:
        found = LocalCallTrace(clock=self.frozen_at()).calls_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert found == ()

    def test_two_features_that_happen_to_share_a_slice_id_are_told_apart_by_their_repo_and_issue(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        other_feature = HarnessCallMother.of_the_implementer_of_another_feature()
        trace.record(other_feature)

        found = trace.calls_of(
            repo=HarnessCallMother.OTHER_REPO, issue=HarnessCallMother.OTHER_ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert [call.session for call in found] == [other_feature.session]


class TestReadingBackWhatWasWritten:
    def test_a_line_written_by_this_program_is_read_back_as_the_same_call(self) -> None:
        written = HarnessCallPayload.from_call(HarnessCallMother.of_the_judge(), ts=_STAMP.isoformat())

        read_back = HarnessCallPayload.from_dict(written.to_contract())

        assert read_back == written


class TestARowOfTheRetiredUnderstandStep:
    def test_a_row_written_when_the_run_still_understood_is_read_back_as_the_understand_step(self) -> None:
        written = HarnessCallPayload.from_call(HarnessCallMother.of_the_implementer(), ts=_STAMP.isoformat())
        row = {**written.to_contract(), "step": "understand"}

        assert HarnessCallPayload.from_dict(row).step is Step.UNDERSTAND


class TestWhereTheTraceLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCallTrace(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(HarnessCallMother.of_the_judge())

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "calls.jsonl").exists()

    def test_the_ledger_path_is_composed_under_runs_and_not_under_the_retired_log_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        path = DurableLedger(name=LocalCallTrace.LEDGER, row=HarnessCallPayload).path()

        assert path == tmp_path / "slice-runner" / "runs" / "calls.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_recording_a_call_reaches_only_the_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_call_trace, monkeypatch)

        trace = LocalCallTrace(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())

        assert len(created) == 1
        stub = created[0]
        assert stub.name == LocalCallTrace.LEDGER
        assert stub.row is HarnessCallPayload
        assert [call.session for call in stub.appended] == [HarnessCallMother.SESSION_OF_THE_IMPLEMENTER]
        assert not (tmp_path / "slice-runner").exists()

    def test_sessions_of_reads_only_from_the_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        WiredStubLedgers.on(local_call_trace, monkeypatch)

        trace = LocalCallTrace(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,)
        assert not (tmp_path / "slice-runner").exists()


class TestTheRetiredLogDirectoryIsNeverTouched(WithTheDurableStoresOutOfTheRealHome):
    def test_a_session_written_under_the_retired_directory_is_neither_found_nor_touched(self, tmp_path: Path) -> None:
        old_ledger = RetiredLedgerDirectory.path(tmp_path, "calls")
        old_line = (
            json.dumps(
                {
                    "repo": HarnessCallMother.REPO,
                    "issue": HarnessCallMother.ISSUE,
                    "slice_id": HarnessCallMother.SLICE_ID,
                    "step": "implement",
                    "session": "session-from-before-the-move",
                }
            )
            + "\n"
        ).encode("utf-8")
        RetiredLedgerDirectory.seeded_without_opening(old_ledger, old_line)

        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == ()
        assert RetiredLedgerDirectory.read_without_opening(old_ledger) == old_line
