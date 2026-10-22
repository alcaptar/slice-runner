from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import NoConversationRecordedError

if TYPE_CHECKING:
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.conversation import Conversation
    from slice_runner.domain.conversation_log import ConversationLog
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadConversationParams:
    repo: str
    issue: int
    worktree: str
    slice_id: str
    step: Step


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadConversationResult:
    session: str
    conversation: Conversation


class ReadConversation:
    def __init__(self, *, trace: CallTrace, log: ConversationLog) -> None:
        self._trace = trace
        self._log = log

    def execute(self, params: ReadConversationParams) -> ReadConversationResult:
        sessions = self._trace.sessions_of(
            repo=params.repo, issue=params.issue, slice_id=params.slice_id, step=params.step
        )
        if not sessions:
            raise NoConversationRecordedError(
                f"no call of {params.slice_id} ever served {params.step}: the trace has nothing to open"
            )

        session = sessions[-1]

        return ReadConversationResult(
            session=session, conversation=self._log.read(session=session, worktree=params.worktree)
        )
