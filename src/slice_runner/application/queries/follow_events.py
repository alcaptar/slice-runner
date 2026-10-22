from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event import Event
    from slice_runner.domain.event_cursor import EventCursor
    from slice_runner.domain.event_reader import EventReader


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowEventsParams:
    cursor: EventCursor
    snapshot: tuple[Event, ...] = ()
    repo: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowEventsResult:
    snapshot: tuple[Event, ...]
    changes: tuple[Event, ...]
    cursor: EventCursor


class FollowEvents:
    def __init__(self, *, reader: EventReader) -> None:
        self._reader = reader

    def execute(self, params: FollowEventsParams) -> FollowEventsResult:
        batch = self._reader.read_since(params.cursor)
        latest = {event.slice_key: event for event in params.snapshot}
        changes: list[Event] = []
        for event in batch.events:
            if params.repo is not None and event.repo != params.repo:
                continue
            if self._differs_from(latest.get(event.slice_key), event):
                changes.append(event)
            latest[event.slice_key] = event

        return FollowEventsResult(snapshot=tuple(latest.values()), changes=tuple(changes), cursor=batch.cursor)

    @staticmethod
    def _differs_from(previous: Event | None, event: Event) -> bool:
        if previous is None:
            return True

        return (previous.step, previous.closure, previous.round_without_changes) != (
            event.step,
            event.closure,
            event.round_without_changes,
        )
