from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.exceptions import UnreadableMetricsLogError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.severity_count import SeverityCount
from slice_runner.domain.step import Step
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.metrics_ledger_entry import MetricsLedgerEntry
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP
_LEGACY_ROW = Path(__file__).resolve().parents[1] / "payloads" / "legacy-metrics-row.json"


class ReadingARow:
    @staticmethod
    def _read(row: dict[str, object]) -> ClosedSliceRecord:
        return MetricsLedgerEntry.of(MetricsEntryPayload.from_dict(row))


class TestTheRetiredUnderstandDiscards(ReadingARow):
    def test_a_row_carrying_the_understand_discards_is_read_without_error(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["understand_discards"] = 2

        assert self._read(row).slice_id == ClosedSliceMother.SLICE_ID

    def test_a_row_written_now_does_not_carry_them(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        assert "understand_discards" not in row


class TestReadingBackARowThisProgramWrote(ReadingARow):
    def test_the_identity_of_the_slice_is_read_back_whole(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert (record.repo, record.issue, record.slice_id, record.name) == (
            ClosedSliceMother.REPO,
            ClosedSliceMother.ISSUE,
            ClosedSliceMother.SLICE_ID,
            ClosedSliceMother.NAME,
        )
        assert record.ts == _STAMP

    def test_every_closure_of_the_program_is_read_back_as_the_state_it_closed_in(self) -> None:
        for reason in ClosingReason:
            closure = Closure.because_of(reason)
            closed = ClosedSliceMother.closed_as(closure)
            row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()

            record = self._read(row)

            assert record.closure == closure

    @pytest.mark.parametrize(
        ("verdict", "reason"),
        [
            ("blocked-hygiene", ClosingReason.CONTROLS),
            ("blocked-unchanged-diff", ClosingReason.JUDGE),
            ("blocked-leftover-worktree", ClosingReason.WORKTREE),
        ],
    )
    def test_a_row_with_a_verdict_of_a_retired_reason_is_read_as_the_reason_that_replaced_it(
        self, verdict: str, reason: ClosingReason
    ) -> None:
        closed = ClosedSliceMother.closed_as(Closure.because_of(reason))
        row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()
        row["verdict"] = verdict

        record = self._read(row)

        assert record.closure == Closure(state=RunState.BLOCKED, reason=reason)

    @pytest.mark.parametrize("reason", [ClosingReason.CONTROLS, ClosingReason.JUDGE, ClosingReason.WORKTREE])
    def test_a_closure_is_never_written_with_the_verdict_of_a_retired_reason(self, reason: ClosingReason) -> None:
        closed = ClosedSliceMother.closed_as(Closure.because_of(reason))

        row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()

        assert row["verdict"] not in {"blocked-hygiene", "blocked-unchanged-diff", "blocked-leftover-worktree"}

    def test_the_harness_spend_measured_across_every_call_is_read_back_whole(self) -> None:
        closed = ClosedSliceMother.merged_measuring(
            HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
        )
        row = MetricsEntryPayload.from_domain(closed, ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert record.spend is not None
        measured = record.spend
        assert (measured.cost_usd, measured.turns, measured.duration_ms, measured.cache_read_tokens) == (
            closed.spend.cost_usd,
            closed.spend.turns,
            closed.spend.duration_ms,
            closed.spend.cache_read_tokens,
        )

    def test_with_nothing_measured_the_spend_is_absent_and_not_a_zero_one(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring_nothing(), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.spend is None

    def test_the_diff_measured_at_the_verify_that_passed_is_read_back_whole(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring_the_diff(stats), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.diff == stats

    def test_a_closure_with_no_diff_measured_this_invocation_is_read_back_as_no_diff_at_all(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert record.diff is None

    def test_the_discarded_call_of_a_discarded_verdict_is_read_back_whole(self) -> None:
        discarded = DiscardedCallMother.of_a_failed_call()
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_discarding_because_of(discarded), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.discarded_call == discarded

    def test_a_discarded_call_from_a_step_other_than_verify_is_read_back_with_that_step(self) -> None:
        discarded = DiscardedCallMother.of_the_step(Step.IMPLEMENT)
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_discarding_because_of(discarded), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.discarded_call == discarded

    def test_a_discarded_call_for_a_missing_structured_output_is_read_back_with_that_cause(self) -> None:
        discarded = DiscardedCallMother.of_a_missing_structured_output()
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_discarding_because_of(discarded), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.discarded_call == discarded

    def test_the_cause_ci_could_not_be_read_is_read_back_as_the_domain_value_it_came_from(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED),
            ts=_STAMP.isoformat(),
        ).to_contract()

        record = self._read(row)

        assert record.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED

    def test_the_budgets_and_the_models_by_role_travel_untouched_as_the_raw_snapshot_they_were_written_with(
        self,
    ) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert record.budgets == row["budgets"]
        assert record.models_by_role == row["models_by_role"]

    def test_the_effort_by_role_travels_untouched_as_the_raw_snapshot_it_was_written_with(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert record.effort_by_role == {"implement": "high", "verify": "high"}

    def test_a_row_written_before_the_effort_was_recorded_is_read_back_with_no_effort_by_role(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["effort_by_role"]

        record = self._read(row)

        assert record.effort_by_role is None

    def test_a_row_without_a_discard_cause_is_read_back_with_no_discarded_call(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_discarding_because_of(None), ts=_STAMP.isoformat()
        ).to_contract()

        record = self._read(row)

        assert record.discarded_call is None

    def test_the_findings_are_read_back_counted_by_severity_and_not_as_a_single_total(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.vetoed_over(FindingMother.without_line(severity=Severity.HIGH)),
            ts=_STAMP.isoformat(),
        ).to_contract()

        record = self._read(row)

        assert record.findings == SeverityCount(high=1, medium=0, low=0)

    def test_the_count_of_what_was_declared_left_out_is_read_back_whole(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_leaving_out("no cubri el binario", "falta el caso de rename"),
            ts=_STAMP.isoformat(),
        ).to_contract()

        record = self._read(row)

        assert record.declared_debt == 2

    def test_a_closure_whose_declaration_was_never_written_is_read_back_with_no_declared_debt_at_all(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()

        record = self._read(row)

        assert record.declared_debt is None


class TestRejectingAnEarlierGeneration(ReadingARow):
    def test_a_row_written_by_the_generation_that_spoke_spanish_keys_fails_to_read_naming_the_generation(
        self,
    ) -> None:
        row = json.loads(_LEGACY_ROW.read_text(encoding="utf-8"))

        with pytest.raises(UnreadableMetricsLogError, match="generation"):
            self._read(row)

    def test_a_row_carrying_the_debt_key_from_before_it_was_renamed_is_rejected_instead_of_ignored(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["debt"] = 0

        with pytest.raises(UnreadableMetricsLogError, match="debt"):
            self._read(row)

    def test_the_legacy_spanish_verdict_for_a_controls_block_is_rejected_instead_of_translated(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["verdict"] = "bloqueada-puertas"

        with pytest.raises(UnreadableMetricsLogError, match="verdict"):
            self._read(row)

    def test_a_row_carrying_the_legacy_wall_clock_duration_key_is_rejected_instead_of_ignored(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["duracion_s"] = None

        with pytest.raises(UnreadableMetricsLogError, match="duracion_s"):
            self._read(row)

    def test_a_row_carrying_the_legacy_token_cost_key_is_rejected_instead_of_ignored(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["coste_tokens"] = None

        with pytest.raises(UnreadableMetricsLogError, match="coste_tokens"):
            self._read(row)

    def test_a_row_carrying_the_legacy_verify_discard_cause_key_is_rejected_instead_of_ignored(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["descartes_verify_causa"] = "llamada-fallida"

        with pytest.raises(UnreadableMetricsLogError, match="descartes_verify_causa"):
            self._read(row)

    def test_a_harness_group_with_only_the_earlier_four_measures_fails_instead_of_defaulting_the_rest_to_zero(
        self,
    ) -> None:
        spend = HarnessSpendMother.of_the_implementer_call()
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring(spend),
            ts=_STAMP.isoformat(),
        ).to_contract()
        row["harness"] = {
            "cost_usd": spend.cost_usd,
            "turns": spend.turns,
            "duration_ms": spend.duration_ms,
            "cache_read_tokens": spend.cache_read_tokens,
        }

        with pytest.raises(UnreadableMetricsLogError, match="generation"):
            self._read(row)


class TestRejectingCorruption(ReadingARow):
    def test_a_harness_cost_that_is_not_a_number_is_rejected_instead_of_read_back_as_zero(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()),
            ts=_STAMP.isoformat(),
        ).to_contract()
        assert isinstance(row["harness"], dict)
        row["harness"]["cost_usd"] = "free"

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_repo_that_is_not_text_is_rejected_instead_of_read_back_as_empty(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["repo"] = 12345

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_model_list_holding_a_non_string_element_is_rejected_instead_of_dropped(self) -> None:
        row = MetricsEntryPayload.from_domain(
            ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()),
            ts=_STAMP.isoformat(),
        ).to_contract()
        row["models"] = ["sonnet", 7]

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_verdict_outside_the_known_vocabulary_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["verdict"] = "en-desacuerdo"

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_timestamp_that_is_not_iso_formatted_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["ts"] = "not-a-timestamp"

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_row_missing_a_required_field_is_rejected_instead_of_read_back_with_it_at_zero(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["name"]

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_row_without_a_timestamp_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["ts"]

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_row_without_a_verdict_is_rejected_instead_of_skipped(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        del row["verdict"]

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)

    def test_a_key_this_program_never_wrote_is_rejected_instead_of_silently_tolerated(self) -> None:
        row = MetricsEntryPayload.from_domain(ClosedSliceMother.merged(), ts=_STAMP.isoformat()).to_contract()
        row["a_key_this_program_never_wrote"] = "llamada-fallida"

        with pytest.raises(UnreadableMetricsLogError):
            self._read(row)
