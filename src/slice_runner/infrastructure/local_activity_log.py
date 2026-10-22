from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.activity_log import ActivityLog
from slice_runner.infrastructure.activity_ledger import ActivityLedger
from slice_runner.infrastructure.activity_payload import ActivityPayload

if TYPE_CHECKING:
    from slice_runner.domain.activity import Activity
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class LocalActivityLog(ActivityLog):
    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock

    def restart(self, coordinates: SliceCoordinates) -> None:
        ledger = ActivityLedger.of(coordinates).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("", encoding="utf-8")

    def record(self, activity: Activity) -> None:
        ActivityLedger.of(activity.coordinates).append(
            ActivityPayload.from_domain(activity, ts=self._clock.now().isoformat())
        )
