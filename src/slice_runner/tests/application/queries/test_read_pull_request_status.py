from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.read_pull_request_status import (
    ReadPullRequestStatus,
    ReadPullRequestStatusParams,
)
from slice_runner.domain.forum import Forum
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother
from slice_runner.tests.mothers.pull_request_review_mother import PullRequestReviewMother
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother

_REPO = "alcaptar/slice-runner"
_PULL_REQUEST = 61


class TestReadPullRequestStatus:
    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()
        forum.reviews.return_value = ()
        return forum

    @pytest.fixture
    def query(self, forum: Mock) -> ReadPullRequestStatus:
        return ReadPullRequestStatus(forum=forum)

    @staticmethod
    def _params(*, last_reviewed_id: int = 0) -> ReadPullRequestStatusParams:
        return ReadPullRequestStatusParams(repo=_REPO, pull_request=_PULL_REQUEST, last_reviewed_id=last_reviewed_id)

    def test_a_merged_pull_request_reports_merged_with_no_changes_requested(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.pull_request_state.return_value = PullRequestStatusMother.merged()

        result = query.execute(self._params())

        assert (result.state, result.requested_changes) == (PullRequestState.MERGED, ())

    def test_a_closed_pull_request_reports_closed(self, query: ReadPullRequestStatus, forum: Mock) -> None:
        forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        result = query.execute(self._params())

        assert result.state is PullRequestState.CLOSED

    def test_an_open_pull_request_with_no_review_asking_for_a_change_carries_no_changes_requested(
        self, query: ReadPullRequestStatus
    ) -> None:
        result = query.execute(self._params())

        assert (result.state, result.requested_changes) == (PullRequestState.OPEN, ())

    def test_a_merged_pull_request_never_asks_the_forum_for_its_reviews(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.pull_request_state.return_value = PullRequestStatusMother.merged()

        query.execute(self._params())

        assert forum.reviews.call_count == 0

    def test_a_review_asking_for_a_change_is_returned_as_a_requested_change(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(asked="arregla el borde"),)

        result = query.execute(self._params())

        assert result.requested_changes == (RequestedChange(body="arregla el borde"),)

    def test_a_review_that_only_carries_line_comments_is_returned_too(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change_in_a_line_comment(asked="esta linea sobra"),
        )

        result = query.execute(self._params())

        assert result.requested_changes == (
            RequestedChange(
                body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(body="esta linea sobra"),)
            ),
        )

    def test_several_reviews_asking_for_a_change_are_returned_in_the_order_they_were_sent(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change(review_id=102, asked="arregla B"),
            PullRequestReviewMother.asking_for_a_change(review_id=101, asked="arregla A"),
        )

        result = query.execute(self._params())

        assert result.requested_changes == (RequestedChange(body="arregla A"), RequestedChange(body="arregla B"))

    def test_a_review_already_seen_does_not_ask_for_the_change_again(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(review_id=101),)

        result = query.execute(self._params(last_reviewed_id=101))

        assert result.requested_changes == ()

    def test_a_review_sent_after_the_last_one_attended_still_asks_for_the_change(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change(review_id=101),
            PullRequestReviewMother.asking_for_a_change(review_id=150, asked="una segunda vuelta"),
        )

        result = query.execute(self._params(last_reviewed_id=101))

        assert result.requested_changes == (RequestedChange(body="una segunda vuelta"),)

    def test_a_pending_or_approved_or_dismissed_review_asks_for_nothing(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (
            PullRequestReviewMother.approving(),
            PullRequestReviewMother.still_a_draft(),
            PullRequestReviewMother.dismissed(),
        )

        result = query.execute(self._params())

        assert result.requested_changes == ()

    def test_the_returned_last_reviewed_id_is_the_most_recent_of_the_reviews_that_asked_for_a_change(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change(review_id=101, asked="arregla A"),
            PullRequestReviewMother.asking_for_a_change(review_id=150, asked="arregla B"),
        )

        result = query.execute(self._params())

        assert result.last_reviewed_id == 150

    def test_no_change_requested_leaves_the_last_reviewed_id_at_its_default(self, query: ReadPullRequestStatus) -> None:
        result = query.execute(self._params())

        assert result.last_reviewed_id == 0

    def test_the_forum_is_asked_about_the_repo_and_pull_request_the_params_carried(
        self, query: ReadPullRequestStatus, forum: Mock
    ) -> None:
        query.execute(self._params())

        forum.pull_request_state.assert_called_once_with(repo=_REPO, number=_PULL_REQUEST)
