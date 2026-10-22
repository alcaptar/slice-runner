from __future__ import annotations

from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_reader import EventBatch, EventReader
from slice_runner.infrastructure.durable_ledger import ReadableDurableLedger
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.local_event_log import LocalEventLog


class LocalEventReader(EventReader):
    def __init__(self) -> None:
        self._events: ReadableDurableLedger[EventPayload] = ReadableDurableLedger(
            name=LocalEventLog.LEDGER, row=EventPayload
        )

    def read_since(self, cursor: EventCursor) -> EventBatch:
        rows, offset = self._events.rows_from(cursor.offset)

        return EventBatch(events=tuple(row.to_domain() for row in rows), cursor=EventCursor(offset=offset))
