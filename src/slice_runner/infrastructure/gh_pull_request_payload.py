from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field

from slice_runner.domain.branch_pull_request import BranchPullRequest
from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.pull_request_mergeability import PullRequestMergeability
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.pull_request_status import PullRequestStatus
from slice_runner.infrastructure.contract_model import ContractModel


class GhPullRequestState(StrEnum):
    MERGED = "MERGED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class GhPullRequestMergeable(StrEnum):
    MERGEABLE = "MERGEABLE"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"


class GhPullRequestPayload(ContractModel):
    number: int

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable pull request", UnreadableForumError)


class GhPullRequestBranchPayload(ContractModel):
    number: int
    head_ref_name: str = Field(alias="headRefName")

    def to_domain(self) -> BranchPullRequest:
        return BranchPullRequest(branch=self.head_ref_name, number=self.number)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable pull request", UnreadableForumError)


class GhPullRequestStatePayload(ContractModel):
    state: GhPullRequestState
    mergeable: GhPullRequestMergeable

    def to_domain(self) -> PullRequestStatus:
        return PullRequestStatus(state=self._state(), mergeability=self._mergeability())

    def _state(self) -> PullRequestState:
        match self.state:
            case GhPullRequestState.MERGED:
                return PullRequestState.MERGED
            case GhPullRequestState.OPEN:
                return PullRequestState.OPEN
            case GhPullRequestState.CLOSED:
                return PullRequestState.CLOSED

    def _mergeability(self) -> PullRequestMergeability:
        match self.mergeable:
            case GhPullRequestMergeable.MERGEABLE:
                return PullRequestMergeability.MERGEABLE
            case GhPullRequestMergeable.CONFLICTING:
                return PullRequestMergeability.CONFLICTING
            case GhPullRequestMergeable.UNKNOWN:
                return PullRequestMergeability.UNKNOWN

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable pull request state", UnreadableForumError)
