from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from collections.abc import Sequence

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


@dataclass(frozen=True, kw_only=True, slots=True)
class CauseTally:
    label: str
    count: int
    samples: int


@dataclass(frozen=True, kw_only=True, slots=True)
class DiscardsByCause:
    tallies: tuple[CauseTally, ...]

    @classmethod
    def of(cls, records: Sequence[ClosedSliceRecord]) -> DiscardsByCause:
        declared = tuple(
            record.discarded_call.cause
            for record in records
            if record.discarded_call is not None and record.discarded_call.step is Step.VERIFY
        )
        return cls(
            tallies=tuple(
                CauseTally(label=str(cause), count=declared.count(cause), samples=len(declared))
                for cause in DiscardCause
            )
        )
