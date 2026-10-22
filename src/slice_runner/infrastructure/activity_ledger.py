from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.activity_payload import ActivityPayload
from slice_runner.infrastructure.durable_ledger import ReadableDurableLedger

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class ActivityLedger:
    DIRECTORY: ClassVar[str] = "activity"

    @classmethod
    def of(cls, coordinates: SliceCoordinates) -> ReadableDurableLedger[ActivityPayload]:
        name = f"{cls.DIRECTORY}/{coordinates.repo}/{coordinates.issue}/{coordinates.slice_id.text}"

        return ReadableDurableLedger(name=name, row=ActivityPayload)
