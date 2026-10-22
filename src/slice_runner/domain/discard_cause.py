from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.exceptions import InvalidVerdictError, MeasuredCallError, MissingStructuredOutputError


class DiscardCause(StrEnum):
    INCOHERENT_VERDICT = "incoherent-verdict"
    FAILED_CALL = "failed-call"
    NO_STRUCTURED_OUTPUT = "no-structured-output"

    @classmethod
    def of_the_rejection(cls, rejection: MeasuredCallError) -> DiscardCause:
        if isinstance(rejection, InvalidVerdictError):
            return cls.INCOHERENT_VERDICT
        if isinstance(rejection, MissingStructuredOutputError):
            return cls.NO_STRUCTURED_OUTPUT

        return cls.FAILED_CALL
