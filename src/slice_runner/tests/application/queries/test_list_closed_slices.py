from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.list_closed_slices import ListClosedSlices, ListClosedSlicesParams
from slice_runner.domain.closed_slice_scope import ClosedSliceScope
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother

_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
_UNTIL = datetime(2026, 12, 31, tzinfo=UTC)
_SCOPE = ClosedSliceScope.of_a_repo_between(repo="alcaptar/slice-runner", since=_SINCE, until=_UNTIL)
_PARAMS = ListClosedSlicesParams(scope=_SCOPE)


class TestListingTheClosedSlicesOfAWindow:
    @pytest.fixture
    def metrics_log(self) -> Mock:
        metrics_log: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        metrics_log.closed_slices.return_value = (ClosedSliceRecordMother.merged(),)
        return metrics_log

    @pytest.fixture
    def query(self, metrics_log: Mock) -> ListClosedSlices:
        return ListClosedSlices(metrics_log=metrics_log)

    def test_the_metrics_log_is_asked_for_the_scope_it_was_given(
        self, query: ListClosedSlices, metrics_log: Mock
    ) -> None:
        query.execute(_PARAMS)

        metrics_log.closed_slices.assert_called_once_with(_SCOPE)

    def test_the_result_is_what_the_metrics_log_answered(self, query: ListClosedSlices, metrics_log: Mock) -> None:
        result = query.execute(_PARAMS)

        assert result == (ClosedSliceRecordMother.merged(),)

    def test_a_window_with_nothing_recorded_returns_nothing(self, query: ListClosedSlices, metrics_log: Mock) -> None:
        metrics_log.closed_slices.return_value = ()

        result = query.execute(_PARAMS)

        assert result == ()
