from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, Self

from pydantic import model_validator

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.closure import Closure
from slice_runner.domain.event import Event
from slice_runner.domain.exceptions import InvalidClosureError, UnreadableEventLogError
from slice_runner.domain.feature_slice import FeatureSlice
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.follow_reason import FollowReason
from slice_runner.infrastructure.follow_rounds_payload import FollowRoundsPayload
from slice_runner.infrastructure.follow_standing import FollowStanding
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow


class EventPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableEventLogError

    standing: FollowStanding
    reason: FollowReason | None = None
    step: Step | None = None
    rounds: FollowRoundsPayload
    round_without_changes: Literal[True] | None = None
    spend: SpendPayload
    budget_usd: float
    pull_request: int | None = None
    pid: int | None = None
    comparison: str | None = None
    parent: int | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _standing_agrees_with_the_reason_and_the_step(self) -> Self:
        if FollowStanding.of(closure=self._closure(), step=self.step) is not self.standing:
            raise ValueError(f"`standing` {self.standing} does not agree with `reason` and `step`")

        return self

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, event: Event) -> Self:
        coordinates = SliceCoordinates(
            repo=event.repo, issue=event.issue, slice_id=CanonicalSliceId.of_text(event.slice_id)
        )
        reason = event.closure.reason

        return cls._stamped(
            coordinates,
            ts=event.at.isoformat(),
            standing=FollowStanding.of(closure=event.closure, step=event.step),
            reason=None if reason is None else FollowReason.of(reason),
            step=event.step,
            rounds=FollowRoundsPayload.from_domain(event.rounds),
            round_without_changes=True if event.round_without_changes else None,
            spend=SpendPayload.from_domain(event.spend),
            budget_usd=event.budget_usd,
            pull_request=event.pull_request,
            pid=event.pid,
            comparison=event.comparison,
            parent=None if event.feature_slice is None else event.feature_slice.parent,
            name=None if event.feature_slice is None else event.feature_slice.name,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the transitions ledger line is not one this program wrote in this generation", cls.UNREADABLE
        )

    def to_domain(self) -> Event:
        return Event(
            slice_id=self.slice_id,
            repo=self.repo,
            issue=self.issue,
            step=self.step,
            at=datetime.fromisoformat(self.ts),
            spend=self.spend.to_domain(),
            budget_usd=self.budget_usd,
            rounds=self.rounds.to_domain(),
            closure=self._closure(),
            feature_slice=self._feature_slice(),
            round_without_changes=self.round_without_changes is True,
            pull_request=self.pull_request,
            pid=self.pid,
            comparison=self.comparison,
        )

    def _closure(self) -> Closure:
        if self.reason is not None:
            try:
                return Closure.because_of(self.reason.to_closing_reason())
            except InvalidClosureError as error:
                raise ValueError(str(error)) from error
        if self.standing is FollowStanding.MERGED:
            return Closure.merged()

        return Closure.open()

    def _feature_slice(self) -> FeatureSlice | None:
        if self.parent is None or self.name is None:
            return None

        return FeatureSlice(parent=self.parent, name=self.name)
