from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.discards_by_cause import DiscardsByCause
from slice_runner.domain.grouped_metrics import GroupedMetrics
from slice_runner.domain.slice_rates import SliceRates
from slice_runner.domain.spend_averages import SpendAverages

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord

UNKNOWN_LABEL = "unknown"


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSliceMetrics:
    samples: int
    rates: SliceRates
    spend: SpendAverages
    discards: DiscardsByCause
    by_model: tuple[GroupedMetrics, ...]
    by_variant: tuple[GroupedMetrics, ...]

    @classmethod
    def of(cls, records: Sequence[ClosedSliceRecord]) -> ClosedSliceMetrics:
        return cls(
            samples=len(records),
            rates=SliceRates.of(records),
            spend=SpendAverages.of(records),
            discards=DiscardsByCause.of(records),
            by_model=cls._grouped(records, labels_of=lambda record: record.models),
            by_variant=cls._grouped(records, labels_of=lambda record: (record.variant,) if record.variant else ()),
        )

    @staticmethod
    def _grouped(
        records: Sequence[ClosedSliceRecord], *, labels_of: Callable[[ClosedSliceRecord], Sequence[str]]
    ) -> tuple[GroupedMetrics, ...]:
        buckets: dict[str, list[ClosedSliceRecord]] = {}
        for record in records:
            for label in labels_of(record) or (UNKNOWN_LABEL,):
                buckets.setdefault(label, []).append(record)

        return tuple(GroupedMetrics.of(label, rows) for label, rows in sorted(buckets.items()))
