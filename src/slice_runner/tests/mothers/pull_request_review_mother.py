from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.pull_request_review import PullRequestReview
from slice_runner.domain.pull_request_review_state import PullRequestReviewState
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment


class PullRequestReviewMother:
    @classmethod
    def asking_for_a_change(
        cls, *, review_id: int = 101, asked: str = "corrige el manejo de errores"
    ) -> PullRequestReview:
        return cls._commented(review_id=review_id, body=asked)

    @classmethod
    def asking_for_a_change_in_a_line_comment(
        cls, *, review_id: int = 101, asked: str = "esta linea sobra"
    ) -> PullRequestReview:
        return cls._commented(
            review_id=review_id, body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(body=asked),)
        )

    @classmethod
    def asking_for_a_change_with_a_body_and_several_comments(
        cls,
        *,
        review_id: int = 101,
        body: str = "corrige el manejo de errores",
        asked: str = "esta linea sobra",
        also: str = "y de paso mira el nombre",
    ) -> PullRequestReview:
        return cls._commented(
            review_id=review_id,
            body=body,
            comments=(
                PullRequestReviewCommentMother.anchored_to_a_line(body=asked),
                PullRequestReviewCommentMother.anchored_to_a_line(body=also, line=43),
            ),
        )

    @classmethod
    def requesting_changes(cls, *, review_id: int = 104, asked: str = "usa el value object") -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.CHANGES_REQUESTED, body=asked)

    @classmethod
    def approving(cls, *, review_id: int = 105) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.APPROVED, body="se ve bien")

    @classmethod
    def still_a_draft(cls, *, review_id: int = 106) -> PullRequestReview:
        return PullRequestReview(
            id=review_id, state=PullRequestReviewState.PENDING, body="todavia lo estoy escribiendo"
        )

    @classmethod
    def dismissed(cls, *, review_id: int = 107) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.DISMISSED, body="esto ya se descarto")

    @staticmethod
    def _commented(
        *, review_id: int, body: str, comments: tuple[PullRequestReviewComment, ...] = ()
    ) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.COMMENTED, body=body, comments=comments)
