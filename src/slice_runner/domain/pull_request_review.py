from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.pull_request_review_state import PullRequestReviewState

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestReview:
    id: int
    state: PullRequestReviewState
    body: str
    comments: tuple[PullRequestReviewComment, ...] = ()

    @property
    def asks_for_a_change(self) -> bool:
        return self._asks and (bool(self.body.strip()) or bool(self.comments))

    @property
    def _asks(self) -> bool:
        match self.state:
            case PullRequestReviewState.PENDING | PullRequestReviewState.DISMISSED | PullRequestReviewState.APPROVED:
                return False
            case PullRequestReviewState.CHANGES_REQUESTED | PullRequestReviewState.COMMENTED:
                return True
