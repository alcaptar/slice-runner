from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.requested_change import RequestedChange

if TYPE_CHECKING:
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.pull_request_review import PullRequestReview


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadPullRequestStatusParams:
    repo: str
    pull_request: int
    last_reviewed_id: int = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadPullRequestStatusResult:
    state: PullRequestState
    requested_changes: tuple[RequestedChange, ...] = ()
    last_reviewed_id: int = 0


class ReadPullRequestStatus:
    def __init__(self, *, forum: Forum) -> None:
        self._forum = forum

    def execute(self, params: ReadPullRequestStatusParams) -> ReadPullRequestStatusResult:
        status = self._forum.pull_request_state(repo=params.repo, number=params.pull_request)
        if status.state is not PullRequestState.OPEN:
            return ReadPullRequestStatusResult(state=status.state)

        reviews = self._forum.reviews(repo=params.repo, pull_request=params.pull_request)
        pending = self._changes_asked_since(reviews, after=params.last_reviewed_id)
        if not pending:
            return ReadPullRequestStatusResult(state=status.state)

        return ReadPullRequestStatusResult(
            state=status.state,
            requested_changes=tuple(RequestedChange(body=review.body, comments=review.comments) for review in pending),
            last_reviewed_id=pending[-1].id,
        )

    @staticmethod
    def _changes_asked_since(reviews: tuple[PullRequestReview, ...], *, after: int) -> tuple[PullRequestReview, ...]:
        pending = [review for review in reviews if review.asks_for_a_change and review.id > after]

        return tuple(sorted(pending, key=lambda review: review.id))
