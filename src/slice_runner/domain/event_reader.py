from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event import Event
    from slice_runner.domain.event_cursor import EventCursor


@dataclass(frozen=True, kw_only=True, slots=True)
class EventBatch:
    events: tuple[Event, ...]
    cursor: EventCursor


class EventReader(ABC):
    @abstractmethod
    def read_since(self, cursor: EventCursor) -> EventBatch: ...
