from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import ConversationNotFoundError, UnreadableConversationError
from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause
from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, ToolUse, UnrecordedCallToolUse
from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder

if TYPE_CHECKING:
    from slice_runner.domain.conversation_log import ConversationLog
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject
    from slice_runner.infrastructure.tool_use_log import ToolUseLog


class ConversationToolUseRecorder(ToolUseRecorder):
    def __init__(self, *, conversations: ConversationLog, tool_use_log: ToolUseLog) -> None:
        self._conversations = conversations
        self._tool_use_log = tool_use_log

    def record_after(self, subject: HarnessCallSubject, *, step: Step, session: str) -> None:
        try:
            conversation = self._conversations.read(session=session, worktree=subject.worktree)
        except (ConversationNotFoundError, UnreadableConversationError) as unreadable:
            self._tool_use_log.record_unrecorded(
                UnrecordedCallToolUse(
                    coordinates=subject.coordinates,
                    step=step,
                    session=session,
                    cause=UnrecordedConversationCause.of_the_failure(unreadable),
                )
            )
            return

        self._tool_use_log.record(
            HarnessCallToolUse(
                coordinates=subject.coordinates,
                step=step,
                session=session,
                uses=tuple(
                    ToolUse(turn=turn.number, tool=call.name, path=call.path, command=call.command, failed=call.failed)
                    for turn in conversation.turns
                    for call in turn.tool_calls
                ),
            )
        )
