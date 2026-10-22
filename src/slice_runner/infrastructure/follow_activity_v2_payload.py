from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, Self

from slice_runner.domain.exceptions import UnreadableFollowLineError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.follow_actor import FollowActor

if TYPE_CHECKING:
    from slice_runner.domain.observed_activity import ObservedActivity


class FollowActivityV2Payload(ContractModel):
    VERSION: ClassVar[Literal[2]] = 2

    version: Literal[2]
    kind: Literal["activity"]
    ts: int
    repo: str
    issue: int
    slice_id: str
    actor: FollowActor
    tool: str
    target: str

    @classmethod
    def from_domain(cls, observed: ObservedActivity) -> Self:
        activity = observed.activity

        return cls(
            version=cls.VERSION,
            kind="activity",
            ts=int(observed.at.timestamp() * 1000),
            repo=activity.coordinates.repo,
            issue=activity.coordinates.issue,
            slice_id=activity.coordinates.slice_id.text,
            actor=FollowActor.of(activity.actor),
            tool=activity.tool,
            target=activity.target,
        )

    @classmethod
    def from_contract(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "follow line v2 activity", UnreadableFollowLineError)
