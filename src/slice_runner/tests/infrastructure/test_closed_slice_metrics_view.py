from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from slice_runner.domain.closed_slice_metrics import UNKNOWN_LABEL, ClosedSliceMetrics
from slice_runner.domain.closed_slice_scope import ClosedSliceScope
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.role_spend import RoleSpend
from slice_runner.domain.step import Step
from slice_runner.infrastructure.closed_slice_metrics_view import ClosedSliceMetricsView
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord

_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_UNTIL = datetime(2026, 12, 31, tzinfo=UTC)


class RenderingTheView:
    @staticmethod
    def _rendered(
        *,
        repo: str | None = None,
        records: tuple[ClosedSliceRecord, ...] = (),
        role_spend: tuple[RoleSpend, ...] = (),
    ) -> str:
        return ClosedSliceMetricsView.rendered(
            scope=ClosedSliceScope.of_a_repo_between(repo=repo, since=_SINCE, until=_UNTIL),
            records=records,
            role_spend=role_spend,
            metrics=ClosedSliceMetrics.of(records),
        )


class TestTheHeaderOfTheView(RenderingTheView):
    def test_the_scope_and_the_count_of_records_are_declared(self) -> None:
        records = (ClosedSliceRecordMother.merged(), ClosedSliceRecordMother.merged())

        rendered = self._rendered(repo="alcaptar/slice-runner", records=records)

        assert "alcaptar/slice-runner" in rendered
        assert _SINCE.isoformat() in rendered
        assert _UNTIL.isoformat() in rendered
        assert "2" in rendered

    def test_a_scope_with_no_repo_says_every_repo_instead_of_a_blank(self) -> None:
        rendered = self._rendered()

        assert "every repo" in rendered


class TestTheGapsTheDataCannotFill(RenderingTheView):
    def test_the_configuration_gap_is_declared_regardless_of_what_is_in_the_window(self) -> None:
        rendered = self._rendered()

        assert "configuration" in rendered

    def test_the_retired_claims_about_tokens_and_a_resumed_slices_size_no_longer_appear(self) -> None:
        rendered = self._rendered()

        assert "input and output tokens" not in rendered
        assert "diff size" not in rendered
        assert "a resumed slice closes with no size measured" not in rendered


class TestWhatTheLedgerLetsCountTwice(RenderingTheView):
    def test_two_rows_that_close_the_same_slice_are_both_listed_with_their_count(self) -> None:
        first = ClosedSliceRecordMother.merged()
        second = ClosedSliceRecordMother.merged()

        rendered = self._rendered(records=(first, second))

        assert f'data-slice-id="{first.slice_id}" data-rows="2"' in rendered

    def test_a_window_with_no_repeated_slice_says_so_instead_of_omitting_the_section(self) -> None:
        rendered = self._rendered(records=(ClosedSliceRecordMother.merged(),))

        assert "no slice was recorded more than once" in rendered


class TestCostAgainstSize(RenderingTheView):
    def test_a_record_with_both_size_and_spend_measured_is_plotted(self) -> None:
        stats = DiffStats(files_changed=4, lines_added=51, lines_deleted=9)
        record = ClosedSliceRecordMother.merged_measuring_the_diff(stats)

        rendered = self._rendered(records=(record,))

        assert f'data-slice-id="{record.slice_id}" data-lines="60" data-cost-usd="{record.spend.cost_usd}"' in rendered  # type: ignore[union-attr]

    def test_a_record_missing_the_diff_is_left_out_of_this_chart(self) -> None:
        record = ClosedSliceRecordMother.merged()

        rendered = self._rendered(records=(record,))

        assert "data-lines=" not in rendered

    def test_an_empty_chart_says_so_instead_of_rendering_nothing(self) -> None:
        rendered = self._rendered()

        assert "no slice in this window measured both its size and its spend" in rendered


class TestSpendByRole(RenderingTheView):
    def test_one_bar_is_drawn_per_role_with_its_cost(self) -> None:
        role_spend = (
            RoleSpend(step=Step.IMPLEMENT, spend=HarnessSpendMother.of_the_implementer_call()),
            RoleSpend(step=Step.VERIFY, spend=HarnessSpendMother.of_the_judge_call()),
        )

        rendered = self._rendered(role_spend=role_spend)

        assert f'data-step="implement" data-cost-usd="{HarnessSpendMother.of_the_implementer_call().cost_usd}"' in (
            rendered
        )
        assert f'data-step="verify" data-cost-usd="{HarnessSpendMother.of_the_judge_call().cost_usd}"' in rendered

    def test_no_role_spend_says_so_instead_of_rendering_nothing(self) -> None:
        rendered = self._rendered()

        assert "no call was traced in this window" in rendered


class TestHowTheRoundsEvolveOverTime(RenderingTheView):
    def test_every_record_is_plotted_against_its_own_moment_in_chronological_order(self) -> None:
        later = ClosedSliceRecordMother.merged_at(datetime(2026, 6, 1, tzinfo=UTC))
        earlier = ClosedSliceRecordMother.merged_at(datetime(2026, 1, 1, tzinfo=UTC))

        rendered = self._rendered(records=(later, earlier))

        assert rendered.index(earlier.ts.isoformat()) < rendered.index(later.ts.isoformat())

    def test_the_rounds_of_a_record_are_the_sum_of_every_way_back_to_implementing(self) -> None:
        record = ClosedSliceRecordMother.merged_after_retrying(implement_retries=3, verify_retries=1)

        rendered = self._rendered(records=(record,))

        assert f'data-slice-id="{record.slice_id}" data-ts="{record.ts.isoformat()}" data-rounds="3"' in rendered


class TestTheRatesSection(RenderingTheView):
    def test_the_input_and_output_tokens_are_painted_alongside_the_other_spend_measures(self) -> None:
        rendered = self._rendered(records=(ClosedSliceRecordMother.merged(),))

        assert 'data-spend="input_tokens" data-samples="1">input_tokens: 15.0 (1 samples)' in rendered
        assert 'data-spend="output_tokens" data-samples="1">output_tokens: 1200.0 (1 samples)' in rendered

    def test_each_rate_is_painted_with_the_number_of_samples_it_comes_from(self) -> None:
        records = (
            ClosedSliceRecordMother.merged(),
            ClosedSliceRecordMother.closed_as(Closure.because_of(ClosingReason.JUDGE)),
        )

        rendered = self._rendered(records=records)

        assert 'data-rate="verifier_fail" data-samples="2">verifier_fail: 50.0 (2 samples)' in rendered
        assert 'data-rate="first_attempt" data-samples="2">first_attempt: 50.0 (2 samples)' in rendered

    def test_a_measurement_with_no_samples_reads_as_no_data_instead_of_a_zero(self) -> None:
        rendered = self._rendered()

        assert "no data (0 samples)" in rendered
        assert "0.0 (0 samples)" not in rendered

    def test_a_record_declaring_neither_model_nor_variant_is_grouped_under_its_own_unknown_label(self) -> None:
        record = ClosedSliceRecordMother.merged_declaring_no_model_and_no_variant()

        rendered = self._rendered(records=(record,))

        assert f'data-group="model" data-label="{UNKNOWN_LABEL}"' in rendered
        assert f'data-group="variant" data-label="{UNKNOWN_LABEL}"' in rendered
