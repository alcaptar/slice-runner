from __future__ import annotations

from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment


class PullRequestReviewCommentMother:
    PATH: str = "src/slice_runner/domain/run.py"
    LINE: int = 42
    ANCHORED_BODY: str = "esta linea sobra"
    STALE_BODY: str = "esto ya no aplica"

    @classmethod
    def anchored_to_a_line(cls, *, body: str = ANCHORED_BODY, line: int = LINE) -> PullRequestReviewComment:
        return PullRequestReviewComment(body=body, path=cls.PATH, line=line)

    @classmethod
    def without_a_line_because_it_went_stale(cls, *, body: str = STALE_BODY) -> PullRequestReviewComment:
        return PullRequestReviewComment(body=body, path=cls.PATH, line=None)
