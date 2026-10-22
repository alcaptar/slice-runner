from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.activity_reader import ActivityBatch, ActivityReader
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.infrastructure.activity_ledger import ActivityLedger

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class LocalActivityReader(ActivityReader):
    def read_since(self, coordinates: SliceCoordinates, cursor: EventCursor) -> ActivityBatch:
        ledger = ActivityLedger.of(coordinates)
        path = ledger.path()
        offset = cursor.offset if not path.exists() or cursor.offset <= path.stat().st_size else 0
        rows, position = ledger.rows_from(offset)

        return ActivityBatch(activities=tuple(row.to_domain() for row in rows), cursor=EventCursor(offset=position))
