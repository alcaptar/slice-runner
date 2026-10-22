from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.read_conversation import ReadConversation, ReadConversationParams
from slice_runner.domain.call_trace import CallTrace
from slice_runner.domain.conversation_log import ConversationLog
from slice_runner.domain.exceptions import NoConversationRecordedError
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.conversation_mother import ConversationMother

_REPO = "alcaptar/slice-runner"
_ISSUE = 38
_WORKTREE = "/Users/someone/repos/the-slice"
_SLICE = "slice-05"
_PARAMS = ReadConversationParams(repo=_REPO, issue=_ISSUE, worktree=_WORKTREE, slice_id=_SLICE, step=Step.IMPLEMENT)
_SESSION = "779e530f-c285-495c-bbdc-f2896f81fe25"
_RETRIED_SESSION = "cd8b5450-595b-403e-b6a6-a1f2c9af512c"


class TestReadingTheConversationOfASlice:
    @pytest.fixture
    def trace(self) -> Mock:
        trace: Mock = create_autospec(CallTrace, spec_set=True, instance=True)
        trace.sessions_of.return_value = (_SESSION,)
        return trace

    @pytest.fixture
    def log(self) -> Mock:
        log: Mock = create_autospec(ConversationLog, spec_set=True, instance=True)
        log.read.return_value = ConversationMother.with_a_decision_and_a_tool_call()
        return log

    @pytest.fixture
    def query(self, trace: Mock, log: Mock) -> ReadConversation:
        return ReadConversation(trace=trace, log=log)

    def test_the_trace_is_asked_for_the_sessions_of_that_slice_and_step(
        self, query: ReadConversation, trace: Mock
    ) -> None:
        query.execute(_PARAMS)

        trace.sessions_of.assert_called_once_with(repo=_REPO, issue=_ISSUE, slice_id=_SLICE, step=Step.IMPLEMENT)

    def test_the_conversation_read_is_the_one_of_the_session_found_in_the_trace(
        self, query: ReadConversation, log: Mock
    ) -> None:
        query.execute(_PARAMS)

        log.read.assert_called_once_with(session=_SESSION, worktree=_WORKTREE)

    def test_the_result_carries_the_session_and_the_conversation_read(self, query: ReadConversation) -> None:
        result = query.execute(_PARAMS)

        assert result.session == _SESSION
        assert result.conversation == ConversationMother.with_a_decision_and_a_tool_call()

    def test_with_several_calls_recorded_the_latest_one_is_the_one_opened(
        self, query: ReadConversation, trace: Mock, log: Mock
    ) -> None:
        trace.sessions_of.return_value = (_SESSION, _RETRIED_SESSION)

        query.execute(_PARAMS)

        log.read.assert_called_once_with(session=_RETRIED_SESSION, worktree=_WORKTREE)

    def test_a_slice_and_step_with_no_call_ever_traced_raises_instead_of_guessing_a_session(
        self, query: ReadConversation, trace: Mock, log: Mock
    ) -> None:
        trace.sessions_of.return_value = ()

        with pytest.raises(NoConversationRecordedError, match=_SLICE):
            query.execute(_PARAMS)

        log.read.assert_not_called()
