from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from slice_runner.domain.activity import Activity
from slice_runner.domain.activity_actor import ActivityActor
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.observed_activity import ObservedActivity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother


class ActivityMother:
    AT: ClassVar[datetime] = datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC)

    @staticmethod
    def of_the_implementer_editing() -> Activity:
        return Activity(
            coordinates=HarnessCallSpendMother.coordinates(),
            actor=ActivityActor.IMPLEMENTER,
            tool="Edit",
            target="src/slice_runner/domain/closure.py",
        )

    @staticmethod
    def of_the_judge_reading() -> Activity:
        return Activity(
            coordinates=HarnessCallSpendMother.coordinates(),
            actor=ActivityActor.JUDGE,
            tool="Read",
            target="contract/follow-line-v2.json",
        )

    @staticmethod
    def coordinates_of_the_followed_slice() -> SliceCoordinates:
        return SliceCoordinates(
            repo=EventMother.REPO, issue=EventMother.ISSUE, slice_id=CanonicalSliceId.of_text("slice-05")
        )

    @classmethod
    def in_the_followed_slice(cls, *, tool: str, target: str) -> Activity:
        return Activity(
            coordinates=cls.coordinates_of_the_followed_slice(),
            actor=ActivityActor.IMPLEMENTER,
            tool=tool,
            target=target,
        )

    @staticmethod
    def of_another_slice() -> Activity:
        return Activity(
            coordinates=HarnessCallSpendMother.coordinates_of_another_slice(),
            actor=ActivityActor.IMPLEMENTER,
            tool="Write",
            target="hello.py",
        )

    @classmethod
    def observed(cls, activity: Activity) -> ObservedActivity:
        return ObservedActivity(at=cls.AT, activity=activity)
