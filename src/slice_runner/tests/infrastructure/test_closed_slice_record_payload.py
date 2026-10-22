from __future__ import annotations

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.infrastructure.closed_slice_record_payload import ClosedSliceRecordPayload
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother


class TestTheContractEmittedForOneClosedSlice:
    def test_the_identity_and_the_result_travel_in_plain_english_and_not_the_durable_vocabulary(self) -> None:
        record = ClosedSliceRecordMother.merged()

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert (contract["repo"], contract["issue"], contract["slice_id"], contract["name"]) == (
            record.repo,
            record.issue,
            record.slice_id,
            record.name,
        )
        assert contract["state"] == "merged"
        assert contract["ts"] == record.ts.isoformat()

    def test_the_spend_measured_travels_whole(self) -> None:
        record = ClosedSliceRecordMother.merged()

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["spend"] == {
            "cost_usd": record.spend.cost_usd,  # type: ignore[union-attr]
            "turns": record.spend.turns,  # type: ignore[union-attr]
            "duration_ms": record.spend.duration_ms,  # type: ignore[union-attr]
            "cache_read_tokens": record.spend.cache_read_tokens,  # type: ignore[union-attr]
            "input_tokens": record.spend.input_tokens,  # type: ignore[union-attr]
            "output_tokens": record.spend.output_tokens,  # type: ignore[union-attr]
        }

    def test_a_slice_with_nothing_measured_omits_the_spend_instead_of_writing_a_zero_one(self) -> None:
        record = ClosedSliceRecordMother.merged_measuring_nothing()

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert "spend" not in contract

    def test_a_slice_with_no_diff_measured_omits_the_size_instead_of_writing_a_zero_one(self) -> None:
        record = ClosedSliceRecordMother.merged()

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert "diff" not in contract

    def test_the_size_of_the_diff_travels_whole_when_it_was_measured(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        record = ClosedSliceRecordMother.merged_measuring_the_diff(stats)

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["diff"] == {"files_changed": 4, "lines_added": 51, "lines_deleted": 9}

    def test_the_cause_a_verdict_was_discarded_travels_in_the_domains_own_english_vocabulary(self) -> None:
        record = ClosedSliceRecordMother.merged_discarding_because_of(DiscardedCallMother.of_a_failed_call())

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["discarded_call"] == {
            "step": "verify",
            "cause": "failed-call",
            "reason": "claude: command not found",
        }

    def test_the_cause_ci_could_not_be_read_travels_in_the_domains_own_english_vocabulary(self) -> None:
        record = ClosedSliceRecordMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED)

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["ci_indeterminate_cause"] == "command-failed"

    def test_the_discards_of_the_implementation_calls_travel_next_to_verifys(self) -> None:
        record = ClosedSliceRecordMother.merged_after_discarding_harness_calls(implement_discards=1)

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["implement_discards"] == 1
        assert "understand_discards" not in contract

    def test_the_configuration_snapshot_travels_untouched_so_a_field_added_to_it_never_breaks_this_contract(
        self,
    ) -> None:
        record = ClosedSliceRecordMother.merged()

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert (contract["budgets"], contract["models_by_role"]) == (record.budgets, record.models_by_role)


class TestTheEffortEmittedForOneClosedSlice:
    def test_the_effort_of_each_role_travels_untouched(self) -> None:
        record = ClosedSliceRecordMother.merged_with_effort({"implement": "high", "verify": "high"})

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert contract["effort_by_role"] == {"implement": "high", "verify": "high"}

    def test_a_row_written_before_the_effort_was_recorded_emits_it_as_null_instead_of_leaving_the_key_out(self) -> None:
        record = ClosedSliceRecordMother.merged_with_effort(None)

        contract = ClosedSliceRecordPayload.from_domain(record).to_contract()

        assert "effort_by_role" in contract
        assert contract["effort_by_role"] is None
