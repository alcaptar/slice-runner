from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.durable_ledger import LedgerRow

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_scope import ClosedSliceScope
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class StampedRow(LedgerRow):
    ts: str
    repo: str
    issue: int
    slice_id: str

    @classmethod
    def may_belong_to(cls, data: dict[str, object], coordinates: SliceCoordinates) -> bool:
        return cls._matches(
            data,
            {
                "repo": (coordinates.repo,),
                "issue": (coordinates.issue,),
                "slice_id": (coordinates.slice_id.text,),
            },
        )

    @classmethod
    def may_belong_to_the_scope(cls, data: dict[str, object], scope: ClosedSliceScope) -> bool:
        wanted: dict[str, tuple[object, ...]] = {}
        if scope.repo is not None:
            wanted["repo"] = (scope.repo,)
        if scope.issues:
            wanted["issue"] = scope.issues

        return cls._matches(data, wanted)

    @staticmethod
    def _matches(data: dict[str, object], wanted: dict[str, tuple[object, ...]]) -> bool:
        return all(data.get(key) in candidates for key, candidates in wanted.items() if key in data)

    @classmethod
    def _stamped(cls, coordinates: SliceCoordinates, *, ts: str, **fields: object) -> Self:
        return cls.model_validate(
            {
                "ts": ts,
                "repo": coordinates.repo,
                "issue": coordinates.issue,
                "slice_id": coordinates.slice_id.text,
                **fields,
            }
        )
