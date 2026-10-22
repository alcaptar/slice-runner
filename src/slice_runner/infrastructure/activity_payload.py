from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Self

from slice_runner.domain.activity import Activity
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.exceptions import UnreadableActivityLogError
from slice_runner.domain.observed_activity import ObservedActivity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.follow_actor import FollowActor
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow


class ActivityPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableActivityLogError

    actor: FollowActor
    tool: str
    target: str

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, activity: Activity, *, ts: str) -> Self:
        return cls._stamped(
            activity.coordinates,
            ts=ts,
            actor=FollowActor.of(activity.actor),
            tool=activity.tool,
            target=activity.target,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the activity ledger line is not one this program wrote in this generation", cls.UNREADABLE
        )

    def to_domain(self) -> ObservedActivity:
        return ObservedActivity(
            at=datetime.fromisoformat(self.ts),
            activity=Activity(
                coordinates=SliceCoordinates(
                    repo=self.repo, issue=self.issue, slice_id=CanonicalSliceId.of_text(self.slice_id)
                ),
                actor=self.actor.to_activity_actor(),
                tool=self.tool,
                target=self.target,
            ),
        )
