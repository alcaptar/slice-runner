from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class DebtEntry:
    coordinates: SliceCoordinates
    left_out: tuple[str, ...]
