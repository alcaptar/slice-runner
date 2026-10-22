from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class HarnessCallSpendMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 45
    SLICE_ID: ClassVar[str] = "slice-45"
    OTHER_SLICE_ID: ClassVar[str] = "slice-46"
    SESSION_OF_ANOTHER_SLICE: ClassVar[str] = "6f1e2d3c-4b5a-4c6d-8e9f-0a1b2c3d4e5f"

    @classmethod
    def coordinates(cls) -> SliceCoordinates:
        return SliceCoordinates(repo=cls.REPO, issue=cls.ISSUE, slice_id=CanonicalSliceId.of_text(cls.SLICE_ID))

    @classmethod
    def coordinates_of_another_slice(cls) -> SliceCoordinates:
        return SliceCoordinates(repo=cls.REPO, issue=cls.ISSUE, slice_id=CanonicalSliceId.of_text(cls.OTHER_SLICE_ID))

    @classmethod
    def of_the_implementer(cls) -> HarnessCallSpend:
        return HarnessCallSpend(
            coordinates=cls.coordinates(),
            session=HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER,
            spend=HarnessSpendMother.of_the_implementer_call(),
        )

    @classmethod
    def of_the_judge(cls) -> HarnessCallSpend:
        return HarnessCallSpend(
            coordinates=cls.coordinates(),
            session=HarnessEnvelopeMother.SESSION_OF_THE_JUDGE,
            spend=HarnessSpendMother.of_the_judge_call(),
        )

    @classmethod
    def of_another_slice(cls) -> HarnessCallSpend:
        return HarnessCallSpend(
            coordinates=cls.coordinates_of_another_slice(),
            session=cls.SESSION_OF_ANOTHER_SLICE,
            spend=HarnessSpendMother.of_the_implementer_call(),
        )
