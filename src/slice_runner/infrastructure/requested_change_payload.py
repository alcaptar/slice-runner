from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.infrastructure.contract_model import ContractModel


class AnchoredCommentPayload(ContractModel):
    body: str
    path: str
    line: int | None = Field(default=None, strict=True)

    @classmethod
    def from_domain(cls, comment: PullRequestReviewComment) -> Self:
        return cls.model_validate({"body": comment.body, "path": comment.path, "line": comment.line})

    def to_domain(self) -> PullRequestReviewComment:
        return PullRequestReviewComment(body=self.body, path=self.path, line=self.line)


class RequestedChangePayload(ContractModel):
    body: str
    comments: list[AnchoredCommentPayload] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, change: RequestedChange) -> Self:
        return cls.model_validate(
            {
                "body": change.body,
                "comments": [AnchoredCommentPayload.from_domain(comment) for comment in change.comments],
            }
        )

    def to_domain(self) -> RequestedChange:
        return RequestedChange(body=self.body, comments=tuple(comment.to_domain() for comment in self.comments))
