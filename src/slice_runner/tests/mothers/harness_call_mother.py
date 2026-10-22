from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class HarnessCallMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 11
    OTHER_REPO: ClassVar[str] = "alcaptar/another-feature"
    OTHER_ISSUE: ClassVar[int] = 99
    SLICE_ID: ClassVar[str] = "slice-11"
    SLICE_ID_WITH_A_USER_STORY: ClassVar[str] = "PROJ-1234-11"
    SESSION_OF_THE_IMPLEMENTER: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER
    SESSION_OF_THE_JUDGE: ClassVar[str] = HarnessEnvelopeMother.SESSION_OF_THE_JUDGE
    SESSION_OF_ANOTHER_FEATURE: ClassVar[str] = "5e0f7c1a-1a2b-4c3d-9e8f-0a1b2c3d4e5f"
    SESSION_OF_THE_DISCARDED_IMPLEMENTER: ClassVar[str] = "2c3d4e5f-6a7b-4c8d-9e0f-1a2b3c4d5e61"
    SESSION_OF_THE_DISCARDED_VERDICT: ClassVar[str] = "3c4d5e6f-7a8b-4c9d-0e1f-2a3b4c5d6e72"

    @classmethod
    def coordinates(cls) -> SliceCoordinates:
        return SliceCoordinates(repo=cls.REPO, issue=cls.ISSUE, slice_id=CanonicalSliceId.of_text(cls.SLICE_ID))

    @classmethod
    def coordinates_with_a_user_story(cls) -> SliceCoordinates:
        return SliceCoordinates(
            repo=cls.REPO, issue=cls.ISSUE, slice_id=CanonicalSliceId.of_text(cls.SLICE_ID_WITH_A_USER_STORY)
        )

    @classmethod
    def coordinates_of_another_feature(cls) -> SliceCoordinates:
        return SliceCoordinates(
            repo=cls.OTHER_REPO, issue=cls.OTHER_ISSUE, slice_id=CanonicalSliceId.of_text(cls.SLICE_ID)
        )

    @classmethod
    def of_the_implementer(cls) -> HarnessCall:
        return HarnessCall(coordinates=cls.coordinates(), step=Step.IMPLEMENT, session=cls.SESSION_OF_THE_IMPLEMENTER)

    @classmethod
    def of_the_judge(cls) -> HarnessCall:
        return HarnessCall(coordinates=cls.coordinates(), step=Step.VERIFY, session=cls.SESSION_OF_THE_JUDGE)

    @classmethod
    def of_the_discarded_implementer(cls) -> HarnessCall:
        return HarnessCall(
            coordinates=cls.coordinates(), step=Step.IMPLEMENT, session=cls.SESSION_OF_THE_DISCARDED_IMPLEMENTER
        )

    @classmethod
    def of_the_discarded_verdict(cls) -> HarnessCall:
        return HarnessCall(
            coordinates=cls.coordinates(), step=Step.VERIFY, session=cls.SESSION_OF_THE_DISCARDED_VERDICT
        )

    @classmethod
    def of_the_implementer_of_a_slice_with_a_user_story(cls) -> HarnessCall:
        return HarnessCall(
            coordinates=cls.coordinates_with_a_user_story(),
            step=Step.IMPLEMENT,
            session=cls.SESSION_OF_THE_IMPLEMENTER,
        )

    @classmethod
    def of_the_implementer_of_another_feature(cls) -> HarnessCall:
        return HarnessCall(
            coordinates=cls.coordinates_of_another_feature(),
            step=Step.IMPLEMENT,
            session=cls.SESSION_OF_ANOTHER_FEATURE,
        )
