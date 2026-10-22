from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event_cursor import EventCursor
    from slice_runner.domain.observed_activity import ObservedActivity
    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class ActivityBatch:
    activities: tuple[ObservedActivity, ...]
    cursor: EventCursor


class ActivityReader(ABC):
    @abstractmethod
    def read_since(self, coordinates: SliceCoordinates, cursor: EventCursor) -> ActivityBatch: ...
