from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.show_feature_status import ShowFeatureStatus, ShowFeatureStatusParams
from slice_runner.domain.branch_pull_request import BranchPullRequest
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.closed_slice_scope import ClosedSliceScope
from slice_runner.domain.forum import Forum
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.slice_status import SliceStatus
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_REPO = "alcaptar/slice-runner"
_ISSUE = 38

_PARAMS = ShowFeatureStatusParams(repo=_REPO, issue=_ISSUE)


class _SharedQueryFixtures:
    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_requests.return_value = ()
        return forum

    @pytest.fixture
    def metrics(self) -> Mock:
        metrics: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        metrics.closed_slices.return_value = ()
        return metrics

    @pytest.fixture
    def query(self, repository: Mock, forum: Mock, metrics: Mock, spend_log: Mock) -> ShowFeatureStatus:
        return ShowFeatureStatus(repository=repository, forum=forum, metrics=metrics, spend_log=spend_log)


class TestShowFeatureStatus(_SharedQueryFixtures):
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.return_value = ParentIssueMother.of_two_slices()
        repository.read_children.return_value = (SubIssueMother.pending(), SubIssueMother.of_another_repo())
        return repository

    @pytest.fixture
    def spend_log(self) -> Mock:
        spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        spend_log.spend_of_the_slice.return_value = HarnessSpend.nothing()
        return spend_log

    def test_the_children_are_read_with_the_count_the_parent_declared(
        self, query: ShowFeatureStatus, repository: Mock
    ) -> None:
        query.execute(_PARAMS)

        repository.read_children.assert_called_once_with(repo=_REPO, parent=_ISSUE, expected=2)

    def test_one_status_comes_back_per_child_in_the_order_they_were_read(self, query: ShowFeatureStatus) -> None:
        statuses = query.execute(_PARAMS)

        assert statuses == (
            SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=None),
            SliceStatus(sub_issue=SubIssueMother.of_another_repo(), pull_request=None),
        )

    def test_the_pull_requests_are_asked_for_with_every_branch_of_the_children_at_once(
        self, query: ShowFeatureStatus, forum: Mock
    ) -> None:
        query.execute(_PARAMS)

        forum.open_pull_requests.assert_called_once_with(
            repo=_REPO,
            branches=(SubIssueMother.pending().branch, SubIssueMother.of_another_repo().branch),
        )

    def test_a_child_whose_branch_carries_an_open_pull_request_gets_its_number(
        self, query: ShowFeatureStatus, forum: Mock
    ) -> None:
        forum.open_pull_requests.return_value = (BranchPullRequest(branch=SubIssueMother.pending().branch, number=47),)

        statuses = query.execute(_PARAMS)

        assert statuses[0].pull_request == 47
        assert statuses[1].pull_request is None

    @pytest.mark.parametrize("child_count", [2, 10])
    def test_the_number_of_calls_to_the_forum_does_not_grow_with_the_number_of_slices(
        self, query: ShowFeatureStatus, repository: Mock, forum: Mock, child_count: int
    ) -> None:
        repository.read_children.return_value = tuple(
            SubIssueMother.carrying(IssueLabel.PENDING) for _ in range(child_count)
        )

        query.execute(_PARAMS)

        assert forum.open_pull_requests.call_count == 1

    def test_no_write_method_of_the_repository_is_ever_called(self, query: ShowFeatureStatus, repository: Mock) -> None:
        query.execute(_PARAMS)

        assert {name for name, _args, _kwargs in repository.method_calls} <= {"read_parent", "read_children"}

    def test_a_blocked_or_an_aborted_slice_passes_through_instead_of_raising(
        self, query: ShowFeatureStatus, repository: Mock
    ) -> None:
        repository.read_children.return_value = (
            SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci()),
            SubIssueMother.blocked(IssueLabel.ABORTED_BUDGET, RunMother.aborted_for_budget(RunMother.judging().spend)),
        )

        statuses = query.execute(_PARAMS)

        assert len(statuses) == 2

    def test_the_registry_is_asked_for_the_repo_and_the_issues_of_the_children_just_read(
        self, query: ShowFeatureStatus, metrics: Mock
    ) -> None:
        query.execute(_PARAMS)

        metrics.closed_slices.assert_called_once_with(
            ClosedSliceScope.of_these_issues(
                repo=_REPO, issues=(SubIssueMother.pending().number, SubIssueMother.of_another_repo().number)
            )
        )

    def test_a_child_with_a_matching_row_in_the_registry_carries_it_in_its_status(
        self, query: ShowFeatureStatus, metrics: Mock
    ) -> None:
        record = ClosedSliceRecordMother.merged_for_issue(SubIssueMother.pending().number)
        metrics.closed_slices.return_value = (record,)

        statuses = query.execute(_PARAMS)

        assert statuses[0].record == record
        assert statuses[1].record is None

    def test_a_child_without_a_row_in_the_registry_carries_no_record_instead_of_inventing_one(
        self, query: ShowFeatureStatus
    ) -> None:
        statuses = query.execute(_PARAMS)

        assert all(status.record is None for status in statuses)


class TestSpendAcrossInvocations(_SharedQueryFixtures):
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.return_value = ParentIssueMother.of_two_slices()
        repository.read_children.return_value = (
            SubIssueMother.blocked(
                IssueLabel.IN_PROGRESS,
                RunMother.judging_after_spending(HarnessSpendMother.of_the_implementer_call()),
            ),
        )
        return repository

    @pytest.fixture
    def spend_log(self) -> Mock:
        spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        spend_log.spend_of_the_slice.return_value = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )
        return spend_log

    def test_a_child_whose_persisted_run_reflects_only_its_last_invocation_reports_the_spend_of_every_traced_call(
        self, query: ShowFeatureStatus, repository: Mock, spend_log: Mock
    ) -> None:
        statuses = query.execute(_PARAMS)

        child = repository.read_children.return_value[0]
        spend_log.spend_of_the_slice.assert_called_once_with(
            SliceCoordinates(
                repo=_REPO, issue=child.number, slice_id=CanonicalSliceId.of_text(child.slice_id.canonical)
            )
        )
        assert child.run is not None
        assert child.run.spend == HarnessSpendMother.of_the_implementer_call()
        assert statuses[0].spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_a_spend_log_with_nothing_measured_for_the_child_leaves_it_unmeasured_instead_of_a_zero(
        self, query: ShowFeatureStatus, spend_log: Mock
    ) -> None:
        spend_log.spend_of_the_slice.return_value = HarnessSpend.nothing()

        statuses = query.execute(_PARAMS)

        assert not statuses[0].spend.measured
