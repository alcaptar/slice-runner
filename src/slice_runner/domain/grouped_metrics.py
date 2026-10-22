from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.slice_rates import SliceRates
from slice_runner.domain.spend_averages import SpendAverages

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


@dataclass(frozen=True, kw_only=True, slots=True)
class GroupedMetrics:
    label: str
    rates: SliceRates
    spend: SpendAverages

    @classmethod
    def of(cls, label: str, records: Sequence[ClosedSliceRecord]) -> GroupedMetrics:
        return cls(label=label, rates=SliceRates.of(records), spend=SpendAverages.of(records))
