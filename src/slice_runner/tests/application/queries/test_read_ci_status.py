from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.read_ci_status import ReadCiStatus, ReadCiStatusParams
from slice_runner.domain.ci import Ci
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.exceptions import CiCommandFailedError, UnreadableCiError
from slice_runner.domain.forum import Forum
from slice_runner.domain.outcome import Outcome
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother

_REPO = "alcaptar/slice-runner"
_PULL_REQUEST = 61


class TestReadCiStatus:
    @pytest.fixture
    def ci(self) -> Mock:
        ci: Mock = create_autospec(Ci, spec_set=True, instance=True)
        ci.status.return_value = CiStatus.GREEN
        return ci

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()
        return forum

    @pytest.fixture
    def query(self, ci: Mock, forum: Mock) -> ReadCiStatus:
        return ReadCiStatus(ci=ci, forum=forum)

    @staticmethod
    def _params() -> ReadCiStatusParams:
        return ReadCiStatusParams(repo=_REPO, pull_request=_PULL_REQUEST)

    def test_a_green_ci_is_done(self, query: ReadCiStatus, ci: Mock) -> None:
        ci.status.return_value = CiStatus.GREEN

        result = query.execute(self._params())

        assert result.outcome is Outcome.DONE

    def test_a_red_ci_is_failed(self, query: ReadCiStatus, ci: Mock) -> None:
        ci.status.return_value = CiStatus.RED

        result = query.execute(self._params())

        assert result.outcome is Outcome.FAILED

    def test_a_pending_ci_is_pending(self, query: ReadCiStatus, ci: Mock) -> None:
        ci.status.return_value = CiStatus.PENDING

        result = query.execute(self._params())

        assert result.outcome is Outcome.PENDING

    def test_no_checks_against_a_mergeable_pull_request_is_indeterminate_with_no_cause(
        self, query: ReadCiStatus, ci: Mock, forum: Mock
    ) -> None:
        ci.status.return_value = CiStatus.NO_CHECKS
        forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = query.execute(self._params())

        assert (result.outcome, result.indeterminate_cause) == (Outcome.INDETERMINATE, None)

    def test_no_checks_against_a_conflicting_pull_request_is_conflicting_instead_of_indeterminate(
        self, query: ReadCiStatus, ci: Mock, forum: Mock
    ) -> None:
        ci.status.return_value = CiStatus.NO_CHECKS
        forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = query.execute(self._params())

        assert result.outcome is Outcome.CONFLICTING

    def test_a_command_that_fails_is_indeterminate_with_the_command_failed_cause(
        self, query: ReadCiStatus, ci: Mock
    ) -> None:
        ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")

        result = query.execute(self._params())

        assert (result.outcome, result.indeterminate_cause) == (
            Outcome.INDETERMINATE,
            CiIndeterminateCause.COMMAND_FAILED,
        )

    def test_a_response_that_cannot_be_read_is_indeterminate_with_the_unreadable_response_cause(
        self, query: ReadCiStatus, ci: Mock
    ) -> None:
        ci.status.side_effect = UnreadableCiError("gh did not return JSON: not valid")

        result = query.execute(self._params())

        assert (result.outcome, result.indeterminate_cause) == (
            Outcome.INDETERMINATE,
            CiIndeterminateCause.UNREADABLE_RESPONSE,
        )

    def test_a_failed_command_against_a_conflicting_pull_request_closes_as_conflict_and_not_as_indeterminate(
        self, query: ReadCiStatus, ci: Mock, forum: Mock
    ) -> None:
        ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")
        forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = query.execute(self._params())

        assert (result.outcome, result.indeterminate_cause) == (Outcome.CONFLICTING, None)

    def test_a_green_ci_never_asks_the_forum_about_mergeability(
        self, query: ReadCiStatus, ci: Mock, forum: Mock
    ) -> None:
        ci.status.return_value = CiStatus.GREEN

        query.execute(self._params())

        assert forum.pull_request_state.call_count == 0

    def test_the_ci_is_asked_about_the_repo_and_pull_request_the_params_carried(
        self, query: ReadCiStatus, ci: Mock
    ) -> None:
        query.execute(self._params())

        ci.status.assert_called_once_with(repo=_REPO, pull_request=_PULL_REQUEST)
