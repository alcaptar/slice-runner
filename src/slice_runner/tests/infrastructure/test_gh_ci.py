from __future__ import annotations

import json

import pytest

from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.exceptions import CiCommandFailedError, UnreadableCiError
from slice_runner.infrastructure.gh_ci import GhCi
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess

_REPO = "alcaptar/slice-runner"
_PULL_REQUEST = 60
_UNRESOLVED = (
    "GraphQL: Could not resolve to a PullRequest with the number of 999999. "
    "(repository.pullRequest)\nno pull requests found for branch"
)


class TestGhCi:
    @staticmethod
    def _answering(stdout: str, *, code: int = 0, stderr: str = "") -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=code, stdout=stdout, stderr=stderr))

    @staticmethod
    def _checks(*buckets: str) -> str:
        return json.dumps([{"name": f"check-{position}", "bucket": bucket} for position, bucket in enumerate(buckets)])

    def _status(self, process: ScriptedProcess) -> CiStatus:
        return GhCi(call=GhCallDoubles.wired(process)).status(repo=_REPO, pull_request=_PULL_REQUEST)

    def test_it_asks_gh_for_the_checks_of_exactly_this_pull_request_in_this_repo(self) -> None:
        process = self._answering(self._checks("pass"))

        self._status(process)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "pr", "checks", str(_PULL_REQUEST)]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--json") == "name,bucket"

    def test_a_pull_request_with_no_check_at_all_reads_as_no_checks(self) -> None:
        assert self._status(self._answering(self._checks())) is CiStatus.NO_CHECKS

    def test_a_bucket_this_program_does_not_know_is_not_green_but_unknown(self) -> None:
        assert self._status(self._answering(self._checks("pass", "stale"))) is CiStatus.UNKNOWN

    def test_a_failed_or_cancelled_check_reads_as_red_even_next_to_pending_and_passing_ones(self) -> None:
        assert self._status(self._answering(self._checks("pass", "pending", "cancel"))) is CiStatus.RED

    def test_a_pending_check_reads_as_pending_even_next_to_passing_ones(self) -> None:
        assert self._status(self._answering(self._checks("pass", "pending"))) is CiStatus.PENDING

    def test_every_check_skipped_reads_as_no_checks_because_nothing_ran(self) -> None:
        assert self._status(self._answering(self._checks("skipping", "skipping"))) is CiStatus.NO_CHECKS

    def test_an_explicit_all_pass_is_what_reads_as_green(self) -> None:
        assert self._status(self._answering(self._checks("pass", "pass"))) is CiStatus.GREEN

    def test_a_skipped_check_next_to_one_that_passed_does_not_take_the_green_away(self) -> None:
        assert self._status(self._answering(self._checks("pass", "skipping"))) is CiStatus.GREEN

    def test_an_answer_that_is_not_json_raises_the_readable_cause_instead_of_reading_as_unknown_in_silence(
        self,
    ) -> None:
        with pytest.raises(UnreadableCiError):
            self._status(self._answering("no checks reported"))

    def test_an_answer_that_is_json_but_not_an_array_raises_the_readable_cause(self) -> None:
        with pytest.raises(UnreadableCiError):
            self._status(self._answering(json.dumps({"name": "check", "bucket": "pass"})))

    def test_an_array_whose_items_are_not_objects_raises_the_readable_cause(self) -> None:
        with pytest.raises(UnreadableCiError):
            self._status(self._answering(json.dumps(["pass", "pass"])))

    def test_a_check_with_a_key_we_did_not_ask_for_raises_the_readable_cause_instead_of_being_read_around(
        self,
    ) -> None:
        recorded = json.dumps([{"name": "check", "bucket": "pass", "state": "SUCCESS"}])

        with pytest.raises(UnreadableCiError):
            self._status(self._answering(recorded))

    def test_a_non_zero_exit_with_a_real_stderr_raises_the_command_failure_and_never_parses_the_empty_stdout(
        self,
    ) -> None:
        with pytest.raises(CiCommandFailedError) as failure:
            self._status(self._answering("", code=1, stderr=_UNRESOLVED))

        assert _UNRESOLVED in str(failure.value)

    def test_a_transient_failure_is_retried_until_it_succeeds(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="connection reset by peer"),
            ProcessOutput(code=0, stdout=self._checks("pass"), stderr=""),
        )

        assert self._status(process) is CiStatus.GREEN
        assert len(process.calls) == 2

    def test_a_non_transient_failure_is_never_retried(self) -> None:
        process = self._answering("", code=1, stderr=_UNRESOLVED)

        with pytest.raises(CiCommandFailedError):
            self._status(process)

        assert len(process.calls) == 1
