from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.event_cursor import EventCursor

if TYPE_CHECKING:
    from collections.abc import Mapping

    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class ActivityCursors:
    positions: Mapping[SliceCoordinates, EventCursor] = field(default_factory=dict)

    def of(self, coordinates: SliceCoordinates) -> EventCursor:
        return self.positions.get(coordinates, EventCursor.start())

    def moved(self, coordinates: SliceCoordinates, to: EventCursor) -> ActivityCursors:
        return ActivityCursors(positions={**self.positions, coordinates: to})
