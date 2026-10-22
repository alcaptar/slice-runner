from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.infrastructure.follow_transition_v2_payload import FollowTransitionV2Payload

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventFollowJsonReport:
    def __init__(self, *, events: tuple[Event, ...]) -> None:
        self._events = events

    def lines(self) -> tuple[str, ...]:
        return tuple(
            json.dumps(FollowTransitionV2Payload.from_domain(event).to_contract(), ensure_ascii=False)
            for event in self._events
        )
