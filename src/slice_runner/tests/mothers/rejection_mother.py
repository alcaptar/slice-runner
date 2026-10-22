from __future__ import annotations

from slice_runner.domain.exceptions import (
    InvalidHarnessOutputError,
    InvalidImplementationReportError,
    InvalidVerdictError,
    MissingStructuredOutputError,
    PermissionDeniedError,
)
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class RejectionMother:
    @staticmethod
    def incoherent_verdict() -> InvalidVerdictError:
        rejection = InvalidVerdictError("a PASS with a finding of severity high contradicts the rubric")
        rejection.spend = HarnessSpendMother.of_the_judge_call()

        return rejection

    @staticmethod
    def denied_read() -> PermissionDeniedError:
        rejection = PermissionDeniedError("the judge was denied reading the diff")
        rejection.spend = HarnessSpendMother.of_the_judge_call()

        return rejection

    @staticmethod
    def envelope_nobody_could_parse() -> InvalidHarnessOutputError:
        return InvalidHarnessOutputError("the harness returned no JSON (code 1): claude: command not found")

    @staticmethod
    def invalid_implementation_report() -> InvalidImplementationReportError:
        rejection = InvalidImplementationReportError("the implementer did not emit the report the brief asked for")
        rejection.spend = HarnessSpendMother.of_the_implementer_call()

        return rejection

    @staticmethod
    def envelope_without_structured_output() -> MissingStructuredOutputError:
        rejection = MissingStructuredOutputError("the harness envelope has no `structured_output`")
        rejection.spend = HarnessSpendMother.of_the_understanding_call()

        return rejection
