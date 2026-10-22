from __future__ import annotations

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.gh_retry_policy import GhRetryPolicy
from slice_runner.infrastructure.gh_call import GhCall, GhCallOutcome
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import RecordingClock, ScriptedProcess

_ARGV = ["gh", "issue", "view", "1"]
_TRANSIENT = ProcessOutput(code=1, stdout="", stderr="connection reset by peer")
_NON_TRANSIENT = ProcessOutput(code=1, stdout="", stderr="HTTP 404: Not Found")
_SUCCESS = ProcessOutput(code=0, stdout="ok", stderr="")


class TestGhCallRetryingATransientFailure:
    def test_a_transient_failure_followed_by_success_ends_well(self) -> None:
        process = ScriptedProcess(_TRANSIENT, _SUCCESS)
        clock = RecordingClock()
        budgets = Budgets()

        outcome = GhCall(process=process, policy=GhRetryPolicy(budgets=budgets), clock=clock).run(
            _ARGV, safe_to_repeat=True
        )

        assert (outcome.output, outcome.retries) == (_SUCCESS, 1)
        assert clock.slept_seconds == [budgets.seconds_between_gh_retries]

    def test_a_non_transient_failure_is_never_retried(self) -> None:
        process = ScriptedProcess(_NON_TRANSIENT)
        clock = RecordingClock()

        outcome = GhCall(process=process, policy=GhRetryPolicy(budgets=Budgets()), clock=clock).run(
            _ARGV, safe_to_repeat=True
        )

        assert (outcome.output, outcome.retries) == (_NON_TRANSIENT, 0)
        assert clock.slept_seconds == []


class TestGhCallBoundingItsRetries:
    def test_retries_exhaust_instead_of_looping_forever(self) -> None:
        budgets = Budgets(gh_retries=2)
        process = ScriptedProcess(_TRANSIENT, _TRANSIENT, _TRANSIENT)
        clock = RecordingClock()

        outcome = GhCall(process=process, policy=GhRetryPolicy(budgets=budgets), clock=clock).run(
            _ARGV, safe_to_repeat=True
        )

        assert (outcome.output, outcome.retries) == (_TRANSIENT, 2)
        assert len(process.calls) == 3
        assert clock.slept_seconds == [budgets.seconds_between_gh_retries] * 2


class TestGhCallRespectingSafety:
    def test_an_unsafe_call_is_never_repeated_even_on_a_transient_failure(self) -> None:
        process = ScriptedProcess(_TRANSIENT)
        clock = RecordingClock()

        outcome = GhCall(process=process, policy=GhRetryPolicy(budgets=Budgets()), clock=clock).run(
            _ARGV, safe_to_repeat=False
        )

        assert (outcome.output, outcome.retries) == (_TRANSIENT, 0)
        assert len(process.calls) == 1
        assert clock.slept_seconds == []


class TestGhCallOutcomeReason:
    def test_the_reason_names_the_retry_count_when_it_retried(self) -> None:
        outcome = GhCallOutcome(output=ProcessOutput(code=1, stdout="", stderr="boom"), retries=2)

        assert outcome.reason == "boom (retried 2x)"

    def test_the_reason_is_plain_when_it_never_retried(self) -> None:
        outcome = GhCallOutcome(output=ProcessOutput(code=1, stdout="", stderr="boom"), retries=0)

        assert outcome.reason == "boom"
