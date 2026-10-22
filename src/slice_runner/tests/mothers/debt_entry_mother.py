from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.debt_entry import DebtEntry
from slice_runner.domain.slice_coordinates import SliceCoordinates


class DebtEntryMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 451
    SLICE_ID: ClassVar[str] = "slice-02"

    @classmethod
    def of_the_slice(
        cls,
        *,
        repo: str | None = None,
        issue: int | None = None,
        slice_id: str | None = None,
        left_out: tuple[str, ...] = (),
    ) -> DebtEntry:
        return DebtEntry(coordinates=cls.coordinates(repo=repo, issue=issue, slice_id=slice_id), left_out=left_out)

    @classmethod
    def coordinates(
        cls, *, repo: str | None = None, issue: int | None = None, slice_id: str | None = None
    ) -> SliceCoordinates:
        return SliceCoordinates(
            repo=repo or cls.REPO,
            issue=cls.ISSUE if issue is None else issue,
            slice_id=CanonicalSliceId.of_text(slice_id or cls.SLICE_ID),
        )
