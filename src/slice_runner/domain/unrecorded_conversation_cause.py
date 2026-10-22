from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.exceptions import ConversationNotFoundError, UnreadableConversationError


class UnrecordedConversationCause(StrEnum):
    NOT_FOUND = "not-found"
    UNREADABLE = "unreadable"

    @classmethod
    def of_the_failure(
        cls, error: ConversationNotFoundError | UnreadableConversationError
    ) -> UnrecordedConversationCause:
        if isinstance(error, ConversationNotFoundError):
            return cls.NOT_FOUND

        return cls.UNREADABLE
