from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, Self

from pydantic import model_validator

from slice_runner.domain.exceptions import UnreadableFollowLineError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.follow_reason import FollowReason
from slice_runner.infrastructure.follow_rounds_payload import FollowRoundsPayload
from slice_runner.infrastructure.follow_standing import FollowStanding

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class FollowTransitionV2Payload(ContractModel):
    VERSION: ClassVar[Literal[2]] = 2

    version: Literal[2]
    kind: Literal["transition"]
    ts: int
    repo: str
    issue: int
    parent: int | None = None
    slice_id: str
    name: str | None = None
    standing: FollowStanding
    reason: FollowReason | None = None
    step: Step | None = None
    rounds: FollowRoundsPayload
    round_without_changes: Literal[True] | None = None
    pull_request: int | None = None
    pid: int | None = None
    comparison: str | None = None
    cost_usd: float
    budget_usd: float

    @model_validator(mode="after")
    def _reason_and_step_agree_with_the_standing(self) -> Self:
        if self.reason is None and self.standing in {FollowStanding.BLOCKED, FollowStanding.ABORTED}:
            raise ValueError(f"`reason` is required when standing is {self.standing}")
        if self.reason is not None and self.reason.standing is not self.standing:
            raise ValueError(f"`reason` {self.reason} does not belong to standing {self.standing}")
        if self.standing is FollowStanding.PENDING and self.step is not None:
            raise ValueError("`step` must be absent when standing is pending")
        if self.standing is not FollowStanding.PENDING and self.step is None:
            raise ValueError(f"`step` is required when standing is {self.standing}")

        return self

    @classmethod
    def from_domain(cls, event: Event) -> Self:
        reason = event.closure.reason
        feature = event.feature_slice

        return cls(
            version=cls.VERSION,
            kind="transition",
            ts=int(event.at.timestamp() * 1000),
            repo=event.repo,
            issue=event.issue,
            parent=None if feature is None else feature.parent,
            slice_id=event.slice_id,
            name=None if feature is None else feature.name,
            standing=FollowStanding.of(closure=event.closure, step=event.step),
            reason=None if reason is None else FollowReason.of(reason),
            step=event.step,
            rounds=FollowRoundsPayload.from_domain(event.rounds),
            round_without_changes=True if event.round_without_changes else None,
            pull_request=event.pull_request,
            pid=event.pid,
            comparison=event.comparison,
            cost_usd=event.spend.cost_usd,
            budget_usd=event.budget_usd,
        )

    @classmethod
    def from_contract(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "follow line v2 transition", UnreadableFollowLineError)
