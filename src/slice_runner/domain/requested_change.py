from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment


@dataclass(frozen=True, kw_only=True, slots=True)
class RequestedChange:
    body: str
    comments: tuple[PullRequestReviewComment, ...] = ()
