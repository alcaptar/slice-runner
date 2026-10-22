from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.run_prechecks import RunPrechecks, RunPrechecksParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.domain.forum import Forum
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/slice-runner"
_ROOT = "/repos/slice-runner"
_BRANCH = "slice/05-prechecks-deterministas"
_BASE = "master"


class TestRunPrechecks:
    @pytest.fixture
    def branches(self) -> Mock:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.commits_behind_remote.return_value = 0
        return branches

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_request.return_value = None
        return forum

    @pytest.fixture
    def query(self, branches: Mock, forum: Mock) -> RunPrechecks:
        return RunPrechecks(branches=branches, forum=forum)

    @staticmethod
    def _params(*, subissue: SubIssue, parent: ParentIssue) -> RunPrechecksParams:
        return RunPrechecksParams(repo=_REPO, root=_ROOT, branch=_BRANCH, base=_BASE, subissue=subissue, parent=parent)

    def test_a_closed_subissue_wins_even_with_everything_else_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.closed(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.SUBISSUE_ALREADY_CLOSED

    def test_a_slice_of_another_repo_is_refused_before_anything_measured_against_this_one_is_believed(
        self, query: RunPrechecks, forum: Mock
    ) -> None:
        forum.open_pull_request.return_value = 47
        params = self._params(
            subissue=SubIssueMother.of_another_repo(), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params).outcome is PrecheckOutcome.SLICE_IN_ANOTHER_REPO

    def test_an_open_pull_request_is_its_own_reason(self, query: RunPrechecks, forum: Mock) -> None:
        forum.open_pull_request.return_value = 47
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN

    def test_a_base_that_does_not_resolve_against_its_remote_is_its_own_reason(
        self, query: RunPrechecks, branches: Mock
    ) -> None:
        branches.commits_behind_remote.side_effect = UnresolvableBaseError(f"{_BASE} does not resolve")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.BASE_NOT_ON_REMOTE

    def test_the_base_the_params_carried_is_what_gets_asked_about(self, query: RunPrechecks, branches: Mock) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        query.execute(params)

        branches.commits_behind_remote.assert_called_once_with(worktree=_ROOT, base=_BASE)

    def test_a_parent_with_no_sources_is_missing_sources(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_sources())

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_SOURCES

    def test_a_parent_with_sources_and_no_controls_is_missing_controls(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_controls())

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_CONTROLS

    def test_a_subissue_with_no_decision_line_is_missing_decisions(self, query: RunPrechecks) -> None:
        params = self._params(
            subissue=SubIssueMother.without_decisions(), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_DECISIONS

    def test_a_parent_with_no_line_under_its_decisions_is_missing_decisions(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_decisions())

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_DECISIONS

    def test_a_subissue_whose_only_decision_is_its_exemption_is_clear(self, query: RunPrechecks) -> None:
        params = self._params(
            subissue=SubIssueMother.exempt_from_decisions(), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_a_parent_whose_only_decision_is_its_exemption_is_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.exempt_from_decisions())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_everything_in_its_place_is_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_a_declared_exemption_is_clear_even_though_it_carries_no_command_to_run(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_exempt_controls())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_the_ports_are_asked_about_the_root_the_branch_and_the_repo_the_params_carried(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        query.execute(params)

        branches.commits_behind_remote.assert_called_once_with(worktree=_ROOT, base=_BASE)
        forum.open_pull_request.assert_called_once_with(repo=_REPO, branch=_BRANCH)


class TestRunPrechecksOfTheDesignsASubissueNames:
    @pytest.fixture
    def query(self) -> RunPrechecks:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.commits_behind_remote.return_value = 0
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_request.return_value = None

        return RunPrechecks(branches=branches, forum=forum)

    @staticmethod
    def _params(*, subissue: SubIssue, parent: ParentIssue) -> RunPrechecksParams:
        return RunPrechecksParams(repo=_REPO, root=_ROOT, branch=_BRANCH, base=_BASE, subissue=subissue, parent=parent)

    def test_a_design_the_parent_does_not_declare_is_its_own_reason(self, query: RunPrechecks) -> None:
        params = self._params(
            subissue=SubIssueMother.naming_designs("tablero", "inexistente"),
            parent=ParentIssueMother.declaring_two_designs(),
        )

        assert query.execute(params).outcome is PrecheckOutcome.UNKNOWN_DESIGN

    def test_a_design_named_while_the_parent_declares_none_is_unknown_too(self, query: RunPrechecks) -> None:
        params = self._params(
            subissue=SubIssueMother.naming_designs("tablero"), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params).outcome is PrecheckOutcome.UNKNOWN_DESIGN

    def test_designs_the_parent_does_declare_are_clear(self, query: RunPrechecks) -> None:
        params = self._params(
            subissue=SubIssueMother.naming_designs("tablero", "detalle"),
            parent=ParentIssueMother.declaring_two_designs(),
        )

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_a_subissue_that_names_no_design_is_clear_even_if_the_parent_declares_some(
        self, query: RunPrechecks
    ) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.declaring_two_designs())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR
