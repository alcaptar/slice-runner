from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.pull_request_review import PullRequestReview
from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment
from slice_runner.domain.pull_request_review_state import PullRequestReviewState
from slice_runner.infrastructure.contract_model import ContractModel


class GhPullRequestReviewState(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class GhPullRequestReviewPayload(ContractModel):
    id: int
    state: GhPullRequestReviewState
    body: str

    def to_domain(self, *, comments: tuple[PullRequestReviewComment, ...]) -> PullRequestReview:
        return PullRequestReview(id=self.id, state=self._state(), body=self.body, comments=comments)

    def _state(self) -> PullRequestReviewState:
        match self.state:
            case GhPullRequestReviewState.APPROVED:
                return PullRequestReviewState.APPROVED
            case GhPullRequestReviewState.CHANGES_REQUESTED:
                return PullRequestReviewState.CHANGES_REQUESTED
            case GhPullRequestReviewState.COMMENTED:
                return PullRequestReviewState.COMMENTED
            case GhPullRequestReviewState.DISMISSED:
                return PullRequestReviewState.DISMISSED
            case GhPullRequestReviewState.PENDING:
                return PullRequestReviewState.PENDING

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(id=data.get("id"), state=data.get("state"), body=data.get("body")),
            "gh returned a review this program cannot read",
            UnreadableForumError,
        )


class GhPullRequestReviewCommentPayload(ContractModel):
    body: str
    path: str
    pull_request_review_id: int
    line: int | None = Field(default=None, strict=True)

    def to_domain(self) -> PullRequestReviewComment:
        return PullRequestReviewComment(body=self.body, path=self.path, line=self.line)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(
                body=data.get("body"),
                path=data.get("path"),
                pull_request_review_id=data.get("pull_request_review_id"),
                line=data.get("line"),
            ),
            "gh returned a pull request comment this program cannot read",
            UnreadableForumError,
        )
