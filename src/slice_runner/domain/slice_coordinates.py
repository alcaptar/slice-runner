from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.canonical_slice_id import CanonicalSliceId


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceCoordinates:
    repo: str
    issue: int
    slice_id: CanonicalSliceId
