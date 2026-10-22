from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.event_log import EventLog
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.event_payload import EventPayload

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class LocalEventLog(EventLog):
    LEDGER: ClassVar[str] = "transitions"

    def __init__(self) -> None:
        self._events: DurableLedger[EventPayload] = DurableLedger(name=self.LEDGER, row=EventPayload)

    def emit(self, event: Event) -> None:
        payload = EventPayload.from_domain(event)
        self._events.append(payload)
        print(json.dumps(payload.to_contract(), ensure_ascii=False), file=sys.stderr)
