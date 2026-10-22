from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.measurement import Measurement

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


@dataclass(frozen=True, kw_only=True, slots=True)
class SpendAverages:
    cost_usd: Measurement
    turns: Measurement
    duration_ms: Measurement
    cache_read_tokens: Measurement
    input_tokens: Measurement
    output_tokens: Measurement

    @classmethod
    def of(cls, records: Sequence[ClosedSliceRecord]) -> SpendAverages:
        measured = tuple(record.spend for record in records if record.spend is not None)
        return cls(
            cost_usd=Measurement.of_the_mean([spend.cost_usd for spend in measured]),
            turns=Measurement.of_the_mean([float(spend.turns) for spend in measured]),
            duration_ms=Measurement.of_the_mean([float(spend.duration_ms) for spend in measured]),
            cache_read_tokens=Measurement.of_the_mean([float(spend.cache_read_tokens) for spend in measured]),
            input_tokens=Measurement.of_the_mean([float(spend.input_tokens) for spend in measured]),
            output_tokens=Measurement.of_the_mean([float(spend.output_tokens) for spend in measured]),
        )
