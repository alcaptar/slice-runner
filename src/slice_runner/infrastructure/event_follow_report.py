from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.follow_reason import FollowReason
from slice_runner.infrastructure.follow_standing import FollowStanding

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventFollowReport:
    def __init__(self, *, events: tuple[Event, ...]) -> None:
        self._events = events

    def lines(self) -> tuple[str, ...]:
        return tuple(self._line_of(event) for event in self._events)

    @staticmethod
    def _line_of(event: Event) -> str:
        step = "-" if event.step is None else event.step
        standing = str(FollowStanding.of(closure=event.closure, step=event.step))
        if event.closure.reason is not None:
            standing = f"{standing} {FollowReason.of(event.closure.reason)}"

        return (
            f"{event.at.isoformat()} {event.repo} #{event.issue} {event.slice_id} "
            f"{step} {standing} ${event.spend.cost_usd:.2f}"
        )
