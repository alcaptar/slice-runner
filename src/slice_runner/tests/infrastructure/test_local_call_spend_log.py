from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.exceptions import UnreadableCallSpendLogError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure import local_call_spend_log
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.infrastructure.retired_ledger_directory import RetiredLedgerDirectory
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother

if TYPE_CHECKING:
    from pathlib import Path

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class WrittenLedger:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "spend.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestWhatIsWrittenDownOfACall(WithTheDurableStoresOutOfTheRealHome):
    def test_a_call_is_written_as_the_run_it_came_from_its_session_and_what_the_harness_spent_on_it(
        self, tmp_path: Path
    ) -> None:
        call = HarnessCallSpendMother.of_the_implementer()

        LocalCallSpendLog(clock=self.frozen_at()).record(call)

        assert WrittenLedger.records_under(tmp_path) == [
            {
                "repo": call.coordinates.repo,
                "issue": call.coordinates.issue,
                "slice_id": call.coordinates.slice_id.text,
                "session": call.session,
                "ts": _STAMP.isoformat(),
                "spend": {
                    "cost_usd": call.spend.cost_usd,
                    "turns": call.spend.turns,
                    "duration_ms": call.spend.duration_ms,
                    "calls": call.spend.calls,
                    "models": list(call.spend.models),
                    "input_tokens": call.spend.input_tokens,
                    "output_tokens": call.spend.output_tokens,
                    "cache_creation_tokens": call.spend.cache_creation_tokens,
                    "cache_read_tokens": call.spend.cache_read_tokens,
                    "ttft_ms": call.spend.ttft_ms,
                    "duration_api_ms": call.spend.duration_api_ms,
                },
            }
        ]


class TestTheLedgerOnlyGrows(WithTheDurableStoresOutOfTheRealHome):
    def test_the_two_calls_of_a_slice_are_both_kept_so_the_judge_does_not_overwrite_the_implementer(
        self, tmp_path: Path
    ) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())

        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_judge())

        assert [record["session"] for record in WrittenLedger.records_under(tmp_path)] == [
            HarnessCallSpendMother.of_the_implementer().session,
            HarnessCallSpendMother.of_the_judge().session,
        ]


class TestAddingUpTheSpendOfSomeSessions(WithTheDurableStoresOutOfTheRealHome):
    def test_the_spend_of_a_single_session_asked_for_is_returned(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())

        found = ledger.spend_of((HarnessCallSpendMother.of_the_implementer().session,))

        assert found == HarnessSpendMother.of_the_implementer_call()

    def test_a_session_not_asked_for_is_left_out_of_the_sum(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_judge())

        found = ledger.spend_of((HarnessCallSpendMother.of_the_implementer().session,))

        assert found == HarnessSpendMother.of_the_implementer_call()

    def test_the_sessions_of_several_calls_are_added_together_so_a_role_split_needs_no_manual_subtraction(
        self, tmp_path: Path
    ) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_judge())

        found = ledger.spend_of(
            (HarnessCallSpendMother.of_the_implementer().session, HarnessCallSpendMother.of_the_judge().session)
        )

        assert found == HarnessSpend.summing(
            [HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()]
        )

    def test_the_sessions_of_several_calls_add_each_new_token_field_on_its_own_side(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_judge())
        implementer = HarnessSpendMother.of_the_implementer_call()
        judge = HarnessSpendMother.of_the_judge_call()

        found = ledger.spend_of(
            (HarnessCallSpendMother.of_the_implementer().session, HarnessCallSpendMother.of_the_judge().session)
        )

        assert (found.input_tokens, found.output_tokens, found.cache_creation_tokens) == (
            implementer.input_tokens + judge.input_tokens,
            implementer.output_tokens + judge.output_tokens,
            implementer.cache_creation_tokens + judge.cache_creation_tokens,
        )

    def test_no_session_matching_returns_nothing_measured_instead_of_a_zero(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())

        found = ledger.spend_of(("session-never-recorded",))

        assert found == HarnessSpend.nothing()

    def test_a_ledger_never_written_returns_nothing_instead_of_failing(self, tmp_path: Path) -> None:
        found = LocalCallSpendLog(clock=self.frozen_at()).spend_of(
            (HarnessCallSpendMother.of_the_implementer().session,)
        )

        assert found == HarnessSpend.nothing()

    def test_a_line_from_before_this_run_carried_identity_is_rejected_instead_of_summed_by_accident(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "spend.jsonl"
        ledger.parent.mkdir(parents=True)
        old_call = HarnessCallSpendMother.of_the_implementer()
        old_line = CallSpendPayload.from_call(old_call, ts=_STAMP.isoformat()).model_dump(
            mode="json", exclude={"repo", "issue", "ts"}
        )
        ledger.write_text(json.dumps(old_line) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallSpendLogError):
            LocalCallSpendLog(clock=self.frozen_at()).spend_of((old_call.session,))

    def test_a_line_that_is_not_json_is_refused_instead_of_being_skipped_in_silence(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "spend.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("not json\n", encoding="utf-8")

        with pytest.raises(UnreadableCallSpendLogError):
            LocalCallSpendLog(clock=self.frozen_at()).spend_of((HarnessCallSpendMother.of_the_implementer().session,))

    def test_a_line_this_program_did_not_write_is_refused_instead_of_being_skipped_in_silence(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "spend.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"session": "some-session"}) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallSpendLogError):
            LocalCallSpendLog(clock=self.frozen_at()).spend_of((HarnessCallSpendMother.of_the_implementer().session,))


class TestAddingUpTheSpendOfASlice(WithTheDurableStoresOutOfTheRealHome):
    def test_the_spend_of_a_slice_is_summed_by_reading_only_the_spend_ledger(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_judge())
        ledger.record(HarnessCallSpendMother.of_another_slice())

        found = ledger.spend_of_the_slice(HarnessCallSpendMother.coordinates())

        assert found == HarnessSpend.summing(
            [HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()]
        )

    def test_a_slice_never_recorded_returns_nothing_measured_instead_of_a_zero(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_another_slice())

        found = ledger.spend_of_the_slice(HarnessCallSpendMother.coordinates())

        assert found == HarnessSpend.nothing()

    def test_a_session_written_twice_by_a_stale_reinvocation_is_summed_only_once(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())
        ledger.record(HarnessCallSpendMother.of_the_implementer())

        found = ledger.spend_of_the_slice(HarnessCallSpendMother.coordinates())

        assert found == HarnessSpendMother.of_the_implementer_call()

    def test_a_line_of_an_earlier_generation_belonging_to_another_slice_does_not_block_reading_this_one(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "spend.jsonl"
        ledger.parent.mkdir(parents=True)
        earlier = {"session": "older-session", "spend": {"cost_usd": 1.0}, "repo": "org/other", "issue": 7}
        ledger.write_text(json.dumps(earlier) + "\n", encoding="utf-8")
        log = LocalCallSpendLog(clock=self.frozen_at())
        log.record(HarnessCallSpendMother.of_the_implementer())

        found = log.spend_of_the_slice(HarnessCallSpendMother.coordinates())

        assert found == HarnessSpendMother.of_the_implementer_call()

    def test_a_line_of_an_earlier_generation_belonging_to_this_slice_is_still_refused(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "spend.jsonl"
        ledger.parent.mkdir(parents=True)
        wanted = HarnessCallSpendMother.coordinates()
        mine_but_earlier = {
            "session": "older-session",
            "repo": wanted.repo,
            "issue": wanted.issue,
            "slice_id": wanted.slice_id.text,
        }
        ledger.write_text(json.dumps(mine_but_earlier) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallSpendLogError, match="generation"):
            LocalCallSpendLog(clock=self.frozen_at()).spend_of_the_slice(wanted)

    def test_a_corrupted_call_trace_ledger_never_gets_in_the_way_because_it_is_never_opened(
        self, tmp_path: Path
    ) -> None:
        calls_ledger = tmp_path / "slice-runner" / "runs" / "calls.jsonl"
        calls_ledger.parent.mkdir(parents=True)
        calls_ledger.write_text("not json\n", encoding="utf-8")
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_implementer())

        found = ledger.spend_of_the_slice(HarnessCallSpendMother.coordinates())

        assert found == HarnessSpendMother.of_the_implementer_call()


class TestASessionDuplicatedInTheLedgerIsCountedOnce(WithTheDurableStoresOutOfTheRealHome):
    def test_a_session_written_twice_by_a_stale_reinvocation_is_summed_only_once(self, tmp_path: Path) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        call = HarnessCallSpendMother.of_the_implementer()
        ledger.record(call)
        ledger.record(call)

        found = ledger.spend_of((call.session,))

        assert found == HarnessSpendMother.of_the_implementer_call()

    def test_a_session_duplicated_on_disk_does_not_inflate_the_sum_of_a_slice_with_other_sessions(
        self, tmp_path: Path
    ) -> None:
        ledger = LocalCallSpendLog(clock=self.frozen_at())
        duplicated = HarnessCallSpendMother.of_the_implementer()
        ledger.record(duplicated)
        ledger.record(duplicated)
        ledger.record(HarnessCallSpendMother.of_the_judge())

        found = ledger.spend_of((duplicated.session, HarnessCallSpendMother.of_the_judge().session))

        assert found == HarnessSpend.summing(
            [HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()]
        )


class TestTheRetiredLogDirectoryIsNeverTouched(WithTheDurableStoresOutOfTheRealHome):
    def test_a_spend_written_under_the_retired_directory_is_neither_found_nor_touched(self, tmp_path: Path) -> None:
        old_ledger = RetiredLedgerDirectory.path(tmp_path, "spend")
        old_call = HarnessCallSpendMother.of_the_implementer()
        old_line = (
            json.dumps(
                CallSpendPayload.from_call(old_call, ts=_STAMP.isoformat()).model_dump(
                    mode="json", exclude={"repo", "issue", "ts"}
                )
            )
            + "\n"
        ).encode("utf-8")
        RetiredLedgerDirectory.seeded_without_opening(old_ledger, old_line)

        found = LocalCallSpendLog(clock=self.frozen_at()).spend_of((old_call.session,))

        assert found == HarnessSpend.nothing()
        assert RetiredLedgerDirectory.read_without_opening(old_ledger) == old_line


class TestARealEnvelopeReachesTheLedger(WithTheDurableStoresOutOfTheRealHome):
    def test_the_tokens_and_the_latencies_a_real_envelope_brings_survive_to_the_durable_ledger(
        self, tmp_path: Path
    ) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded("full-recipe")).to_domain()
        call = HarnessCallSpend(
            coordinates=HarnessCallSpendMother.coordinates(),
            session=HarnessEnvelopeMother.SESSION_OF_THE_JUDGE,
            spend=spend,
        )
        ledger = LocalCallSpendLog(clock=self.frozen_at())

        ledger.record(call)

        found = ledger.spend_of((call.session,))
        assert (
            found.input_tokens,
            found.output_tokens,
            found.cache_creation_tokens,
            found.cache_read_tokens,
            found.ttft_ms,
            found.duration_api_ms,
        ) == (17, 3443, 16547, 15510, 5384, 28905)


class TestReadingBackWhatWasWritten:
    def test_a_line_written_by_this_program_is_read_back_as_the_same_call(self) -> None:
        written = CallSpendPayload.from_call(HarnessCallSpendMother.of_the_judge(), ts=_STAMP.isoformat())

        read_back = CallSpendPayload.from_dict(written.to_contract())

        assert read_back == written


class TestWhereTheLedgerLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCallSpendLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(
            HarnessCallSpendMother.of_the_judge()
        )

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "spend.jsonl").exists()

    def test_the_ledger_path_is_composed_under_runs_and_not_under_the_retired_log_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        path = DurableLedger(name=LocalCallSpendLog.LEDGER, row=CallSpendPayload).path()

        assert path == tmp_path / "slice-runner" / "runs" / "spend.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_recording_a_call_reaches_only_the_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_call_spend_log, monkeypatch)

        LocalCallSpendLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(
            HarnessCallSpendMother.of_the_judge()
        )

        assert len(created) == 1
        stub = created[0]
        assert stub.name == LocalCallSpendLog.LEDGER
        assert stub.row is CallSpendPayload
        assert [call.session for call in stub.appended] == [HarnessCallSpendMother.of_the_judge().session]
        assert not (tmp_path / "slice-runner").exists()

    def test_spend_of_reads_only_from_the_ledger_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        WiredStubLedgers.on(local_call_spend_log, monkeypatch)

        ledger = LocalCallSpendLog(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at())
        ledger.record(HarnessCallSpendMother.of_the_judge())

        found = ledger.spend_of((HarnessCallSpendMother.of_the_judge().session,))

        assert found == HarnessSpendMother.of_the_judge_call()
        assert not (tmp_path / "slice-runner").exists()
