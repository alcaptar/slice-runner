from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, kw_only=True, slots=True)
class Measurement:
    value: float | None
    samples: int

    @classmethod
    def of_the_fraction(cls, part: int, whole: int) -> Measurement:
        if whole == 0:
            return cls(value=None, samples=0)

        return cls(value=round(100.0 * part / whole, 1), samples=whole)

    @classmethod
    def of_the_mean(cls, values: Sequence[float]) -> Measurement:
        if not values:
            return cls(value=None, samples=0)

        return cls(value=round(sum(values) / len(values), 2), samples=len(values))
