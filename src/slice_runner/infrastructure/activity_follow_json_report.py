from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.infrastructure.follow_activity_v2_payload import FollowActivityV2Payload

if TYPE_CHECKING:
    from slice_runner.domain.observed_activity import ObservedActivity


class ActivityFollowJsonReport:
    def __init__(self, *, activities: tuple[ObservedActivity, ...]) -> None:
        self._activities = activities

    def lines(self) -> tuple[str, ...]:
        return tuple(
            json.dumps(FollowActivityV2Payload.from_domain(observed).to_contract(), ensure_ascii=False)
            for observed in self._activities
        )
