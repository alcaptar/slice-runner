from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates

if TYPE_CHECKING:
    from slice_runner.domain.activity_cursors import ActivityCursors
    from slice_runner.domain.activity_reader import ActivityReader
    from slice_runner.domain.event import Event
    from slice_runner.domain.observed_activity import ObservedActivity


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowActivityParams:
    snapshot: tuple[Event, ...]
    cursors: ActivityCursors


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowActivityResult:
    activities: tuple[ObservedActivity, ...]
    cursors: ActivityCursors


class FollowActivity:
    def __init__(self, *, reader: ActivityReader) -> None:
        self._reader = reader

    def execute(self, params: FollowActivityParams) -> FollowActivityResult:
        cursors = params.cursors
        activities: list[ObservedActivity] = []
        for event in params.snapshot:
            coordinates = SliceCoordinates(
                repo=event.repo, issue=event.issue, slice_id=CanonicalSliceId.of_text(event.slice_id)
            )
            batch = self._reader.read_since(coordinates, cursors.of(coordinates))
            activities.extend(batch.activities)
            cursors = cursors.moved(coordinates, batch.cursor)

        return FollowActivityResult(activities=tuple(activities), cursors=cursors)
