from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.exceptions import CiCommandFailedError, UnreadableCiError


class CiIndeterminateCause(StrEnum):
    COMMAND_FAILED = "command-failed"
    UNREADABLE_RESPONSE = "unreadable-response"

    @classmethod
    def of_the_failure(cls, error: CiCommandFailedError | UnreadableCiError) -> CiIndeterminateCause:
        if isinstance(error, CiCommandFailedError):
            return cls.COMMAND_FAILED

        return cls.UNREADABLE_RESPONSE
