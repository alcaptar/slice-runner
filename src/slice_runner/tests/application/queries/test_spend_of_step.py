from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.spend_of_step import SpendOfStep, SpendOfStepParams
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother

_REPO = "alcaptar/slice-runner"
_ISSUE = 38
_SLICE = "slice-05"
_PARAMS = SpendOfStepParams(repo=_REPO, issue=_ISSUE, slice_id=_SLICE, step=Step.IMPLEMENT)
_SESSION = "779e530f-c285-495c-bbdc-f2896f81fe25"
_RETRIED_SESSION = "cd8b5450-595b-403e-b6a6-a1f2c9af512c"


class TestAddingUpWhatARoleSpentOnASlice:
    @pytest.fixture
    def trace(self) -> Mock:
        trace: Mock = create_autospec(CallTrace, spec_set=True, instance=True)
        trace.sessions_of.return_value = (_SESSION,)
        return trace

    @pytest.fixture
    def spend_log(self) -> Mock:
        spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        spend_log.spend_of.return_value = HarnessSpendMother.of_the_implementer_call()
        return spend_log

    @pytest.fixture
    def query(self, trace: Mock, spend_log: Mock) -> SpendOfStep:
        return SpendOfStep(trace=trace, spend_log=spend_log)

    def test_the_trace_is_asked_for_the_sessions_of_that_slice_and_step(self, query: SpendOfStep, trace: Mock) -> None:
        query.execute(_PARAMS)

        trace.sessions_of.assert_called_once_with(repo=_REPO, issue=_ISSUE, slice_id=_SLICE, step=Step.IMPLEMENT)

    def test_the_spend_log_is_asked_to_sum_the_sessions_found_in_the_trace(
        self, query: SpendOfStep, trace: Mock, spend_log: Mock
    ) -> None:
        trace.sessions_of.return_value = (_SESSION, _RETRIED_SESSION)

        query.execute(_PARAMS)

        spend_log.spend_of.assert_called_once_with((_SESSION, _RETRIED_SESSION))

    def test_the_result_is_the_sum_the_spend_log_answered(self, query: SpendOfStep, spend_log: Mock) -> None:
        result = query.execute(_PARAMS)

        assert result == HarnessSpendMother.of_the_implementer_call()

    def test_a_slice_and_step_with_no_call_ever_traced_asks_the_spend_log_to_sum_nothing(
        self, query: SpendOfStep, trace: Mock, spend_log: Mock
    ) -> None:
        trace.sessions_of.return_value = ()
        spend_log.spend_of.return_value = HarnessSpend.nothing()

        result = query.execute(_PARAMS)

        spend_log.spend_of.assert_called_once_with(())
        assert result == HarnessSpend.nothing()
