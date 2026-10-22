from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.check_sources import CheckSources, CheckSourcesParams
from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.source_reader import SourceReader
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother

_WORKTREE = "/repos/slice-runner/.worktrees/05-prechecks-deterministas"


class TestCheckSources:
    @pytest.fixture
    def sources(self) -> Mock:
        sources: Mock = create_autospec(SourceReader, spec_set=True, instance=True)
        sources.read_all.return_value = ()
        return sources

    @pytest.fixture
    def query(self, sources: Mock) -> CheckSources:
        return CheckSources(sources=sources)

    @staticmethod
    def _params() -> CheckSourcesParams:
        return CheckSourcesParams(worktree=_WORKTREE, sources=ParentIssueMother.with_sources_and_controls().sources)

    def test_sources_that_can_all_be_read_are_clear(self, query: CheckSources) -> None:
        result = query.execute(self._params())

        assert (result.outcome, result.reason) == (PrecheckOutcome.CLEAR, None)

    def test_a_declared_source_that_cannot_be_read_is_its_own_reason(self, query: CheckSources, sources: Mock) -> None:
        sources.read_all.side_effect = UnreadableSourceError("CLAUDE.md does not exist under the worktree")

        result = query.execute(self._params())

        assert result.outcome is PrecheckOutcome.UNREADABLE_SOURCE
        assert result.reason == "CLAUDE.md does not exist under the worktree"

    def test_declared_sources_over_the_size_budget_are_their_own_reason(
        self, query: CheckSources, sources: Mock
    ) -> None:
        sources.read_all.side_effect = SourcesBudgetExceededError("the declared sources are over budget")

        result = query.execute(self._params())

        assert result.outcome is PrecheckOutcome.SOURCES_OVER_BUDGET
        assert result.reason == "the declared sources are over budget"

    def test_the_sources_are_read_from_the_worktree_the_params_carried(
        self, query: CheckSources, sources: Mock
    ) -> None:
        params = self._params()

        query.execute(params)

        sources.read_all.assert_called_once_with(worktree=_WORKTREE, sources=params.sources)

    def test_the_designs_the_params_carried_travel_to_the_reader_so_they_count_against_the_same_budget(
        self, query: CheckSources, sources: Mock
    ) -> None:
        params = replace(self._params(), designs=(DesignMother.board(),))

        query.execute(params)

        sources.read_all.assert_called_once_with(
            worktree=_WORKTREE, sources=params.sources, designs=(DesignMother.board(),)
        )
