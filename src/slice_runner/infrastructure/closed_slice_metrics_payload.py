from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_metrics import ClosedSliceMetrics
    from slice_runner.domain.discards_by_cause import CauseTally
    from slice_runner.domain.grouped_metrics import GroupedMetrics
    from slice_runner.domain.measurement import Measurement
    from slice_runner.domain.slice_rates import SliceRates
    from slice_runner.domain.spend_averages import SpendAverages


class MeasurementPayload(ContractModel):
    value: float | None
    samples: int

    @classmethod
    def from_domain(cls, measurement: Measurement) -> Self:
        return cls(value=measurement.value, samples=measurement.samples)


class SliceRatesPayload(ContractModel):
    verifier_fail: MeasurementPayload
    blocked_by_controls: MeasurementPayload
    first_attempt: MeasurementPayload
    implement_retries: MeasurementPayload
    verify_discards: MeasurementPayload
    ci_red: MeasurementPayload

    @classmethod
    def from_domain(cls, rates: SliceRates) -> Self:
        return cls(
            verifier_fail=MeasurementPayload.from_domain(rates.verifier_fail),
            blocked_by_controls=MeasurementPayload.from_domain(rates.blocked_by_controls),
            first_attempt=MeasurementPayload.from_domain(rates.first_attempt),
            implement_retries=MeasurementPayload.from_domain(rates.implement_retries),
            verify_discards=MeasurementPayload.from_domain(rates.verify_discards),
            ci_red=MeasurementPayload.from_domain(rates.ci_red),
        )


class SpendAveragesPayload(ContractModel):
    cost_usd: MeasurementPayload
    turns: MeasurementPayload
    duration_ms: MeasurementPayload
    cache_read_tokens: MeasurementPayload
    input_tokens: MeasurementPayload
    output_tokens: MeasurementPayload

    @classmethod
    def from_domain(cls, spend: SpendAverages) -> Self:
        return cls(
            cost_usd=MeasurementPayload.from_domain(spend.cost_usd),
            turns=MeasurementPayload.from_domain(spend.turns),
            duration_ms=MeasurementPayload.from_domain(spend.duration_ms),
            cache_read_tokens=MeasurementPayload.from_domain(spend.cache_read_tokens),
            input_tokens=MeasurementPayload.from_domain(spend.input_tokens),
            output_tokens=MeasurementPayload.from_domain(spend.output_tokens),
        )


class CauseTallyPayload(ContractModel):
    cause: str
    count: int
    samples: int

    @classmethod
    def from_domain(cls, tally: CauseTally) -> Self:
        return cls(cause=tally.label, count=tally.count, samples=tally.samples)


class GroupedMetricsPayload(ContractModel):
    label: str
    rates: SliceRatesPayload
    spend: SpendAveragesPayload

    @classmethod
    def from_domain(cls, grouped: GroupedMetrics) -> Self:
        return cls(
            label=grouped.label,
            rates=SliceRatesPayload.from_domain(grouped.rates),
            spend=SpendAveragesPayload.from_domain(grouped.spend),
        )


class ClosedSliceMetricsPayload(ContractModel):
    samples: int
    rates: SliceRatesPayload
    spend: SpendAveragesPayload
    discards_by_cause: tuple[CauseTallyPayload, ...]
    by_model: tuple[GroupedMetricsPayload, ...]
    by_variant: tuple[GroupedMetricsPayload, ...]

    @classmethod
    def from_domain(cls, metrics: ClosedSliceMetrics) -> Self:
        return cls(
            samples=metrics.samples,
            rates=SliceRatesPayload.from_domain(metrics.rates),
            spend=SpendAveragesPayload.from_domain(metrics.spend),
            discards_by_cause=tuple(CauseTallyPayload.from_domain(tally) for tally in metrics.discards.tallies),
            by_model=tuple(GroupedMetricsPayload.from_domain(group) for group in metrics.by_model),
            by_variant=tuple(GroupedMetricsPayload.from_domain(group) for group in metrics.by_variant),
        )
