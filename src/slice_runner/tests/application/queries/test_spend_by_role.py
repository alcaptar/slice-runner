from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.spend_by_role import SpendByRole, SpendByRoleParams
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother

_RECORD = ClosedSliceRecordMother.merged()
_PARAMS = SpendByRoleParams(records=(_RECORD,))


class TestAddingUpWhatEachRoleSpentAcrossASetOfSlices:
    @pytest.fixture
    def trace(self) -> Mock:
        trace: Mock = create_autospec(CallTrace, spec_set=True, instance=True)
        trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(), HarnessCallMother.of_the_judge())
        return trace

    @pytest.fixture
    def spend_log(self) -> Mock:
        spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        spend_log.spend_of.side_effect = [
            HarnessSpendMother.of_the_implementer_call(),
            HarnessSpendMother.of_the_judge_call(),
        ]
        return spend_log

    @pytest.fixture
    def query(self, trace: Mock, spend_log: Mock) -> SpendByRole:
        return SpendByRole(trace=trace, spend_log=spend_log)

    def test_the_trace_is_asked_for_the_calls_of_every_record_given(self, query: SpendByRole, trace: Mock) -> None:
        query.execute(_PARAMS)

        trace.calls_of.assert_called_once_with(repo=_RECORD.repo, issue=_RECORD.issue, slice_id=_RECORD.slice_id)

    def test_a_spend_is_returned_for_each_step_that_had_a_call(self, query: SpendByRole) -> None:
        result = query.execute(_PARAMS)

        assert {entry.step for entry in result} == {Step.IMPLEMENT, Step.VERIFY}

    def test_the_spend_of_a_step_is_the_sum_of_the_sessions_of_that_step(
        self, query: SpendByRole, spend_log: Mock
    ) -> None:
        result = query.execute(_PARAMS)

        by_step = {entry.step: entry.spend for entry in result}
        assert by_step[Step.IMPLEMENT] == HarnessSpendMother.of_the_implementer_call()
        assert by_step[Step.VERIFY] == HarnessSpendMother.of_the_judge_call()

    def test_two_records_that_both_used_the_same_step_have_their_sessions_summed_together(
        self, trace: Mock, spend_log: Mock
    ) -> None:
        trace.calls_of.return_value = (HarnessCallMother.of_the_implementer(),)
        spend_log.spend_of.side_effect = None
        spend_log.spend_of.return_value = HarnessSpendMother.of_the_implementer_call()
        query = SpendByRole(trace=trace, spend_log=spend_log)
        other = ClosedSliceRecordMother.closed_as(_RECORD.closure)

        query.execute(SpendByRoleParams(records=(_RECORD, other)))

        assert spend_log.spend_of.call_count == 1
        (sessions,) = spend_log.spend_of.call_args.args
        assert set(sessions) == {HarnessCallMother.SESSION_OF_THE_IMPLEMENTER}

    def test_no_records_asks_nothing_and_returns_nothing(self, spend_log: Mock) -> None:
        trace: Mock = create_autospec(CallTrace, spec_set=True, instance=True)
        query = SpendByRole(trace=trace, spend_log=spend_log)

        result = query.execute(SpendByRoleParams(records=()))

        trace.calls_of.assert_not_called()
        spend_log.spend_of.assert_not_called()
        assert result == ()

    def test_nothing_measured_for_a_step_still_answers_a_spend_of_zero_instead_of_leaving_it_out(
        self, query: SpendByRole, spend_log: Mock
    ) -> None:
        spend_log.spend_of.side_effect = None
        spend_log.spend_of.return_value = HarnessSpend.nothing()

        result = query.execute(_PARAMS)

        by_step = {entry.step: entry.spend for entry in result}
        assert by_step[Step.IMPLEMENT] == HarnessSpend.nothing()
