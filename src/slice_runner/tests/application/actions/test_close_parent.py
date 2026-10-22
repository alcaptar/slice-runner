from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.close_parent import CloseParent, CloseParentParams
from slice_runner.domain.run_repository import RunRepository
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_REPO = "alcaptar/slice-runner"
_ISSUE = 38


class TestCloseParent:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.return_value = ParentIssueMother.of_two_slices()
        repository.read_children.return_value = (SubIssueMother.closed(), SubIssueMother.closed())
        return repository

    @pytest.fixture
    def action(self, repository: Mock) -> CloseParent:
        return CloseParent(repository=repository)

    @staticmethod
    def _params() -> CloseParentParams:
        return CloseParentParams(repo=_REPO, issue=_ISSUE)

    def test_the_last_subissue_closing_closes_the_parent_with_the_count_the_graph_reported(
        self, action: CloseParent, repository: Mock
    ) -> None:
        action.execute(self._params())

        repository.close_parent.assert_called_once_with(repo=_REPO, issue=_ISSUE, subissue_count=2)

    def test_a_subissue_still_open_leaves_the_parent_untouched(self, action: CloseParent, repository: Mock) -> None:
        repository.read_children.return_value = (SubIssueMother.closed(), SubIssueMother.pending())

        action.execute(self._params())

        assert repository.close_parent.call_count == 0

    def test_a_parent_already_closed_is_neither_re_closed_nor_read_for_its_children_again(
        self, action: CloseParent, repository: Mock
    ) -> None:
        repository.read_parent.return_value = ParentIssueMother.already_closed()

        action.execute(self._params())

        assert repository.read_children.call_count == 0
        assert repository.close_parent.call_count == 0

    def test_a_feature_with_no_subissue_at_all_is_not_closed_for_lacking_anything_pending(
        self, action: CloseParent, repository: Mock
    ) -> None:
        repository.read_parent.return_value = ParentIssueMother.with_no_subissues()

        action.execute(self._params())

        assert repository.read_children.call_count == 0
        assert repository.close_parent.call_count == 0

    def test_the_children_are_asked_for_with_the_same_parentage_criterion_the_program_runs_them_by(
        self, action: CloseParent, repository: Mock
    ) -> None:
        action.execute(self._params())

        repository.read_children.assert_called_once_with(repo=_REPO, parent=_ISSUE, expected=2)
