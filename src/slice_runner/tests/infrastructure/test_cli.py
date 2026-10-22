from __future__ import annotations

import io
import json
import sys
import tomllib
from dataclasses import replace
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.clock import Clock
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_reader import EventBatch
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.retired_issue_label import RetiredIssueLabel
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.reset_comment import ResetComment
from slice_runner.infrastructure.system_clock import SystemClock
from slice_runner.infrastructure.veto_findings_comment import VetoFindingsComment
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import (
    Answer,
    AnsweringByArgv,
    AnsweringByArgvWithADiffThatMoves,
    MissingExecutableReplacement,
    ProcessDoubles,
    RecordedCall,
    RecordedReplacement,
    ReplacementRequestedError,
    ScriptedEventReader,
    TimingOutProcess,
)
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.entrypoint_process import EntrypointProcess, WithTheEntrypointLaunchingNothing
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.conversation_transcript_mother import ConversationTranscriptMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.transition_request_mother import TransitionRequestMother
from slice_runner.tests.mothers.verify_process_mother import VerifyProcessMother
from slice_runner.tests.run_invocation import RunInvocation

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.run import Run

_SLICE = "slice-01"
_IMPLEMENTER_PAYLOAD = "implementer-two-paths"

_TABLE: list[tuple[Step, Outcome, dict[str, int], tuple[Step, str, int]]] = [
    (Step.MOUNT_WORKTREE, Outcome.DONE, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.MOUNT_WORKTREE, Outcome.OVER_BUDGET, {}, (Step.MOUNT_WORKTREE, "aborted-budget", 0)),
    (
        Step.MOUNT_WORKTREE,
        Outcome.CONFLICTING,
        {},
        (Step.MOUNT_WORKTREE, "blocked-ci-conflict", 0),
    ),
    (
        Step.MOUNT_WORKTREE,
        Outcome.WORKTREE_TAKEN,
        {},
        (Step.MOUNT_WORKTREE, "blocked-worktree", 0),
    ),
    (Step.UNDERSTAND, Outcome.WORKTREE_TAKEN, {}, (Step.UNDERSTAND, "blocked-worktree", 0)),
    (Step.IMPLEMENT, Outcome.WORKTREE_TAKEN, {}, (Step.IMPLEMENT, "blocked-worktree", 0)),
    (Step.RUN_CONTROLS, Outcome.WORKTREE_TAKEN, {}, (Step.RUN_CONTROLS, "blocked-worktree", 0)),
    (Step.VERIFY, Outcome.WORKTREE_TAKEN, {}, (Step.VERIFY, "blocked-worktree", 0)),
    (
        Step.OPEN_PULL_REQUEST,
        Outcome.WORKTREE_TAKEN,
        {},
        (Step.OPEN_PULL_REQUEST, "blocked-worktree", 0),
    ),
    (Step.AWAIT_CI, Outcome.WORKTREE_TAKEN, {}, (Step.AWAIT_CI, "blocked-worktree", 0)),
    (Step.CATCH_UP, Outcome.WORKTREE_TAKEN, {}, (Step.CATCH_UP, "blocked-worktree", 0)),
    (Step.AWAIT_MERGE, Outcome.WORKTREE_TAKEN, {}, (Step.AWAIT_MERGE, "blocked-worktree", 0)),
    (
        Step.MOUNT_WORKTREE,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.MOUNT_WORKTREE, "blocked-worktree", 0),
    ),
    (
        Step.UNDERSTAND,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.UNDERSTAND, "blocked-worktree", 0),
    ),
    (
        Step.IMPLEMENT,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.IMPLEMENT, "blocked-worktree", 0),
    ),
    (
        Step.RUN_CONTROLS,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.RUN_CONTROLS, "blocked-worktree", 0),
    ),
    (
        Step.VERIFY,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.VERIFY, "blocked-worktree", 0),
    ),
    (
        Step.OPEN_PULL_REQUEST,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.OPEN_PULL_REQUEST, "blocked-worktree", 0),
    ),
    (
        Step.AWAIT_CI,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.AWAIT_CI, "blocked-worktree", 0),
    ),
    (
        Step.CATCH_UP,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.CATCH_UP, "blocked-worktree", 0),
    ),
    (
        Step.AWAIT_MERGE,
        Outcome.WORKTREE_LEFT_BEHIND,
        {},
        (Step.AWAIT_MERGE, "blocked-worktree", 0),
    ),
    (Step.UNDERSTAND, Outcome.OVER_BUDGET, {}, (Step.UNDERSTAND, "aborted-budget", 0)),
    (Step.UNDERSTAND, Outcome.CONFLICTING, {}, (Step.UNDERSTAND, "blocked-ci-conflict", 0)),
    (Step.IMPLEMENT, Outcome.DONE, {}, (Step.RUN_CONTROLS, "open", 0)),
    (Step.IMPLEMENT, Outcome.DISCARDED, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.IMPLEMENT, Outcome.OVER_BUDGET, {}, (Step.IMPLEMENT, "aborted-budget", 0)),
    (
        Step.IMPLEMENT,
        Outcome.CALL_NOT_MEASURED,
        {},
        (Step.IMPLEMENT, "aborted-unmeasured-call", 0),
    ),
    (Step.IMPLEMENT, Outcome.CONFLICTING, {}, (Step.IMPLEMENT, "blocked-ci-conflict", 0)),
    (Step.RUN_CONTROLS, Outcome.DONE, {}, (Step.VERIFY, "open", 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.RUN_CONTROLS, Outcome.FAILED, {"control_retries": 1}, (Step.IMPLEMENT, "open", 0)),
    (
        Step.RUN_CONTROLS,
        Outcome.FAILED,
        {"control_retries": 2},
        (Step.RUN_CONTROLS, "blocked-controls", 0),
    ),
    (Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED, {"hygiene_retries": 1}, (Step.IMPLEMENT, "open", 0)),
    (
        Step.RUN_CONTROLS,
        Outcome.HYGIENE_REJECTED,
        {"hygiene_retries": 2},
        (Step.RUN_CONTROLS, "blocked-controls", 0),
    ),
    (Step.RUN_CONTROLS, Outcome.INDETERMINATE, {}, (Step.RUN_CONTROLS, "open", 30)),
    (Step.RUN_CONTROLS, Outcome.INDETERMINATE, {"control_retries": 2}, (Step.RUN_CONTROLS, "open", 30)),
    (Step.RUN_CONTROLS, Outcome.OVER_BUDGET, {}, (Step.RUN_CONTROLS, "aborted-budget", 0)),
    (Step.RUN_CONTROLS, Outcome.CONFLICTING, {}, (Step.RUN_CONTROLS, "blocked-ci-conflict", 0)),
    (Step.VERIFY, Outcome.DONE, {}, (Step.OPEN_PULL_REQUEST, "open", 0)),
    (Step.VERIFY, Outcome.DISCARDED, {}, (Step.VERIFY, "open", 0)),
    (Step.VERIFY, Outcome.FAILED, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 1}, (Step.IMPLEMENT, "open", 0)),
    (Step.VERIFY, Outcome.FAILED, {"verify_retries": 2}, (Step.VERIFY, "blocked-verify", 0)),
    (Step.VERIFY, Outcome.UNCHANGED, {}, (Step.VERIFY, "blocked-verify", 0)),
    (Step.VERIFY, Outcome.OVER_BUDGET, {}, (Step.VERIFY, "aborted-budget", 0)),
    (
        Step.VERIFY,
        Outcome.CALL_NOT_MEASURED,
        {},
        (Step.VERIFY, "aborted-unmeasured-call", 0),
    ),
    (Step.VERIFY, Outcome.CONFLICTING, {}, (Step.VERIFY, "blocked-ci-conflict", 0)),
    (Step.OPEN_PULL_REQUEST, Outcome.DONE, {}, (Step.AWAIT_CI, "open", 0)),
    (
        Step.OPEN_PULL_REQUEST,
        Outcome.OVER_BUDGET,
        {},
        (Step.OPEN_PULL_REQUEST, "aborted-budget", 0),
    ),
    (
        Step.OPEN_PULL_REQUEST,
        Outcome.CONFLICTING,
        {},
        (Step.OPEN_PULL_REQUEST, "blocked-ci-conflict", 0),
    ),
    (Step.AWAIT_CI, Outcome.DONE, {}, (Step.AWAIT_MERGE, "open", 0)),
    (Step.AWAIT_CI, Outcome.PENDING, {}, (Step.AWAIT_CI, "open", 30)),
    (Step.AWAIT_CI, Outcome.INDETERMINATE, {}, (Step.AWAIT_CI, "open", 30)),
    (Step.AWAIT_CI, Outcome.INDETERMINATE, {"indeterminate_ticks": 1}, (Step.AWAIT_CI, "open", 30)),
    (
        Step.AWAIT_CI,
        Outcome.INDETERMINATE,
        {"indeterminate_ticks": Budgets().indeterminate_ticks - 1},
        (Step.AWAIT_CI, "blocked-ci-indeterminate", 0),
    ),
    (Step.AWAIT_CI, Outcome.FAILED, {}, (Step.IMPLEMENT, "open", 0)),
    (Step.AWAIT_CI, Outcome.FAILED, {"ci_retries": 1}, (Step.AWAIT_CI, "blocked-ci-red", 0)),
    (Step.AWAIT_CI, Outcome.OVER_BUDGET, {}, (Step.AWAIT_CI, "aborted-budget", 0)),
    (Step.AWAIT_CI, Outcome.CONFLICTING, {}, (Step.CATCH_UP, "open", 30)),
    (
        Step.AWAIT_CI,
        Outcome.CONFLICTING,
        {"catch_up_retries": Budgets().catch_up_retries},
        (Step.AWAIT_CI, "blocked-ci-conflict", 0),
    ),
    (Step.CATCH_UP, Outcome.DONE, {}, (Step.RUN_CONTROLS, "open", 0)),
    (Step.CATCH_UP, Outcome.CONFLICTING, {}, (Step.CATCH_UP, "blocked-ci-conflict", 0)),
    (Step.CATCH_UP, Outcome.OVER_BUDGET, {}, (Step.CATCH_UP, "aborted-budget", 0)),
    (Step.AWAIT_MERGE, Outcome.DONE, {}, (Step.AWAIT_MERGE, "merged", 0)),
    (Step.AWAIT_MERGE, Outcome.PENDING, {}, (Step.AWAIT_MERGE, "open", 30)),
    (Step.AWAIT_MERGE, Outcome.OVER_BUDGET, {}, (Step.AWAIT_MERGE, "aborted-budget", 0)),
    (Step.AWAIT_MERGE, Outcome.CHANGES_REQUESTED, {}, (Step.IMPLEMENT, "open", 0)),
]

_IMPOSSIBLE: list[tuple[Step, Outcome]] = sorted(
    {(step, outcome) for step in Step for outcome in Outcome} - {(step, outcome) for step, outcome, *_ in _TABLE},
)


@pytest.fixture(autouse=True)
def _every_run_closes_its_metrics_row_outside_the_real_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "durable-metrics"))


@pytest.fixture(autouse=True)
def _every_run_ignores_the_worktrees_inside_a_clone_of_the_test_and_not_of_this_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RunInvocation, "common_dir", tmp_path / "common-git-dir")


class BlindToTheToolboxOfThisMachine:
    @pytest.fixture(autouse=True)
    def toolbox_out_of_reach(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "no-toolbox"))


class ReadingWhatWasReported:
    @staticmethod
    def _reported(capsys: pytest.CaptureFixture[str]) -> str:
        output = capsys.readouterr()
        assert output.out == ""

        return output.err


class ReadingTheJudgeCall:
    @staticmethod
    def _judge_call(process: AnsweringByArgv) -> RecordedCall:
        (call,) = [call for call in process.calls if call.argv[0] == JudgeInvocation.EXECUTABLE]

        return call

    @staticmethod
    def _verified(process: AnsweringByArgv, *, base: str = VerifyProcessMother.BASE, slice_id: str = _SLICE) -> int:
        return Cli(process=process, budgets=Budgets()).verify(
            repo=VerifyProcessMother.WORKTREE, base=base, slice_id=slice_id
        )


class TestTheExitCodeOfTheVerdict(ReadingTheJudgeCall, BlindToTheToolboxOfThisMachine):
    def test_a_pass_exits_with_zero_and_emits_the_verdict_as_json_on_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        code = self._verified(process)

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out) == {"ruling": "PASS", "findings": [], "prior_rulings": []}

    def test_a_fail_exits_with_one_and_emits_every_finding_whoever_retries_the_slice_needs(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.recorded())

        code = self._verified(process)

        assert code == ExitCode.VETOED
        emitted = json.loads(capsys.readouterr().out)
        assert emitted["ruling"] == "FAIL"
        assert [finding["severity"] for finding in emitted["findings"]] == ["high", "high", "medium", "medium"]


class TestWhenThereIsNoVerdictToTrust(ReadingTheJudgeCall, BlindToTheToolboxOfThisMachine):
    def test_an_incoherent_verdict_exits_with_two_instead_of_being_treated_as_a_pass(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding(path="mod.py"))
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.carrying(incoherent))

        code = self._verified(process)

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "PASS with 1 finding" in output.err

    def test_a_judge_that_cannot_be_launched_exits_with_two_instead_of_with_the_code_of_the_veto(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = self._verified(VerifyProcessMother.with_an_unrunnable_judge())

        assert code == ExitCode.NO_USABLE_VERDICT
        output = capsys.readouterr()
        assert output.out == ""
        assert "claude" in output.err


class TestWhenThereIsNothingToJudge(ReadingTheJudgeCall, BlindToTheToolboxOfThisMachine):
    def test_with_nothing_staged_it_exits_with_three_without_spending_an_invocation_of_the_judge(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.with_nothing_staged()

        code = self._verified(process)

        assert code == ExitCode.NO_DIFF
        assert not process.invoked(JudgeInvocation.EXECUTABLE)
        assert "staged" in capsys.readouterr().err

    def test_a_base_that_does_not_resolve_does_not_exit_with_the_code_of_the_empty_index(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.with_a_base_that_does_not_resolve(base="does-not-exist")

        code = self._verified(process, base="does-not-exist")

        assert code == ExitCode.USAGE_ERROR
        assert not process.invoked(JudgeInvocation.EXECUTABLE)
        assert "does-not-exist" in capsys.readouterr().err

    def test_a_repo_that_does_not_resolve_exits_with_four_without_blaming_the_base(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.with_a_worktree_that_is_not_a_repo()

        code = self._verified(process)

        assert code == ExitCode.USAGE_ERROR
        assert not process.invoked(JudgeInvocation.EXECUTABLE)
        assert "the repo or the base" in capsys.readouterr().err

    def test_a_slice_identifier_a_person_typed_wrong_exits_as_a_usage_error_and_not_as_an_interrupted_run(
        self,
    ) -> None:
        process = VerifyProcessMother.judging()

        code = self._verified(process, slice_id="01")

        assert code == ExitCode.USAGE_ERROR
        assert not process.invoked(JudgeInvocation.EXECUTABLE)


class TestTheDiffTheJudgeReads(ReadingTheJudgeCall, BlindToTheToolboxOfThisMachine):
    def test_the_judge_is_handed_the_diff_of_the_index_inside_the_prompt(self) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.recorded())

        self._verified(process)

        assert "+    return 2" in self._judge_call(process).stdin

    def test_no_path_to_a_materialised_patch_travels_because_there_is_no_patch_to_point_at(self) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.recorded())

        self._verified(process)

        assert "slice.diff" not in self._judge_call(process).stdin


class TestWhatTheJudgeWasDeniedReading(ReadingTheJudgeCall, BlindToTheToolboxOfThisMachine):
    def test_a_denied_read_is_warned_about_on_standard_error_because_the_yardstick_may_be_incomplete(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.denying_a_read())

        code = self._verified(process)

        output = capsys.readouterr()
        assert code == ExitCode.OK
        assert HarnessEnvelopeMother.DENIED_READ in output.err
        assert json.loads(output.out) == {"ruling": "PASS", "findings": [], "prior_rulings": []}

    def test_a_run_with_nothing_denied_says_nothing_so_the_warning_keeps_meaning_something(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()))

        self._verified(process)

        assert capsys.readouterr().err == ""


class TestWhatTheJudgeMayRead(ReadingTheJudgeCall):
    @staticmethod
    def _toolbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        toolbox = tmp_path / "toolbox"
        (toolbox / "skills").mkdir(parents=True)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(toolbox))

        return toolbox

    def test_the_toolbox_of_the_machine_is_granted_next_to_the_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = self._toolbox(tmp_path, monkeypatch)
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.recorded())

        self._verified(process)

        assert Argv(self._judge_call(process).argv).values_of("--add-dir") == [
            VerifyProcessMother.WORKTREE,
            str(toolbox / "skills"),
        ]

    def test_what_the_judge_may_read_is_told_to_the_judge_and_not_only_granted_in_the_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        toolbox = self._toolbox(tmp_path, monkeypatch)
        process = VerifyProcessMother.judging(HarnessEnvelopeMother.recorded())

        self._verified(process)

        assert str(toolbox / "skills") in self._judge_call(process).stdin


class TestTheEntrypoint(BlindToTheToolboxOfThisMachine):
    def test_main_wires_the_parsed_arguments_into_the_run(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.with_nothing_staged()
        EntrypointProcess.answering_with(monkeypatch, process)

        code = Cli.main(
            ["verify", "--repo", VerifyProcessMother.WORKTREE, "--base", VerifyProcessMother.BASE, "--slice", _SLICE]
        )

        assert code == ExitCode.NO_DIFF
        assert "staged" in capsys.readouterr().err

    def test_main_reports_the_base_it_was_given_and_not_a_guessed_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = VerifyProcessMother.with_a_base_that_does_not_resolve(base="a-base-that-is-not-there")
        EntrypointProcess.answering_with(monkeypatch, process)

        code = Cli.main(
            ["verify", "--repo", VerifyProcessMother.WORKTREE, "--base", "a-base-that-is-not-there", "--slice", _SLICE]
        )

        assert code == ExitCode.USAGE_ERROR
        assert "a-base-that-is-not-there" in capsys.readouterr().err


class TestAnExceptionNoListInTheProgramDescribes:
    _MESSAGE = "a leak in the plumbing nobody named"

    @staticmethod
    def _explodes(entrypoint: type[Cli], *, request: str, budgets: Budgets) -> int:
        raise RuntimeError(TestAnExceptionNoListInTheProgramDescribes._MESSAGE)

    def test_main_reports_its_type_and_message_and_exits_with_the_code_of_a_run_interrupted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        monkeypatch.setattr(Cli, "explain", classmethod(self._explodes))

        code = Cli.main(["explain"])

        output = capsys.readouterr()
        assert code == ExitCode.RUN_INTERRUPTED
        assert code != ExitCode.VETOED
        assert output.out == ""
        assert f"RuntimeError: {self._MESSAGE}" in output.err


class TestTheCommandThatPrintsAConversation:
    _REPO = "alcaptar/slice-runner"
    _ISSUE = 45
    _SLICE = "slice-05"
    _WORKTREE = ConversationTranscriptMother.WORKTREE

    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @classmethod
    def _coordinates(cls) -> SliceCoordinates:
        return SliceCoordinates(repo=cls._REPO, issue=cls._ISSUE, slice_id=CanonicalSliceId.of_text(cls._SLICE))

    def _traced(self) -> None:
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(
                coordinates=self._coordinates(), step=Step.IMPLEMENT, session=ConversationTranscriptMother.SESSION
            )
        )
        ConversationTranscriptMother.written_under(ClaudeConfig.root())

    def test_the_conversation_of_a_traced_call_is_printed_as_readable_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._traced()

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.OK
        output = capsys.readouterr()
        assert output.err == ""
        assert "Now let's confirm RED before implementing:" in output.out

    def test_a_slice_and_step_never_traced_exits_with_a_usage_error_instead_of_guessing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert self._SLICE in output.err

    def test_a_corrupt_line_in_the_call_trace_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._corrupted(DurableLedger(name=LocalCallTrace.LEDGER, row=HarnessCallPayload).path())

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "not JSON" in output.err

    def test_a_corrupt_line_in_the_conversation_transcript_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._traced()
        self._corrupted(self._transcript_path())

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "not JSON" in output.err

    @staticmethod
    def _transcript_path() -> Path:
        return ConversationTranscriptMother.destination_of(
            ClaudeConfig.root(), session=ConversationTranscriptMother.SESSION
        )

    @staticmethod
    def _corrupted(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json\n", encoding="utf-8")

    def test_a_traced_session_whose_conversation_was_never_kept_exits_with_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(
                coordinates=self._coordinates(), step=Step.IMPLEMENT, session=ConversationTranscriptMother.SESSION
            )
        )

        code = Cli.read(
            repo=self._REPO, issue=self._ISSUE, worktree=self._WORKTREE, slice_id=self._SLICE, step=Step.IMPLEMENT
        )

        assert code == ExitCode.USAGE_ERROR
        assert ConversationTranscriptMother.SESSION in capsys.readouterr().err

    def test_main_wires_the_parsed_arguments_into_the_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced()

        code = Cli.main(
            [
                "read",
                "--repo",
                self._REPO,
                "--issue",
                str(self._ISSUE),
                "--worktree",
                self._WORKTREE,
                "--slice",
                self._SLICE,
                "--step",
                str(Step.IMPLEMENT),
            ]
        )

        assert code == ExitCode.OK
        assert "Now let's confirm RED before implementing:" in capsys.readouterr().out

    def test_the_step_has_no_default_because_a_guessed_one_reads_the_wrong_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                [
                    "read",
                    "--repo",
                    self._REPO,
                    "--issue",
                    str(self._ISSUE),
                    "--worktree",
                    self._WORKTREE,
                    "--slice",
                    self._SLICE,
                ]
            )

        assert "the following arguments are required: --step" in capsys.readouterr().err

    def test_a_step_nobody_declared_is_refused_instead_of_being_forwarded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                [
                    "read",
                    "--repo",
                    self._REPO,
                    "--issue",
                    str(self._ISSUE),
                    "--worktree",
                    self._WORKTREE,
                    "--slice",
                    self._SLICE,
                    "--step",
                    "deploy",
                ]
            )

        assert "invalid choice" in capsys.readouterr().err


class TestTheCommandThatSumsSpendByRole:
    _REPO = "alcaptar/slice-runner"
    _ISSUE = 45
    _SLICE = "slice-05"

    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    def _traced_and_spent(self, *, step: Step, call: HarnessCallSpend) -> None:
        coordinates = SliceCoordinates(
            repo=self._REPO, issue=self._ISSUE, slice_id=CanonicalSliceId.of_text(self._SLICE)
        )
        LocalCallTrace(clock=SystemClock()).record(
            HarnessCall(coordinates=coordinates, step=step, session=call.session)
        )
        LocalCallSpendLog(clock=SystemClock()).record(call)

    def test_the_spend_of_a_traced_call_is_printed_as_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())

        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out)
        assert printed["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert printed["calls"] == 1

    def test_a_slice_and_step_never_traced_prints_nothing_measured_instead_of_failing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out)["calls"] == 0

    def test_a_corrupt_line_in_the_call_trace_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._corrupted(DurableLedger(name=LocalCallTrace.LEDGER, row=HarnessCallPayload).path())

        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "not JSON" in output.err

    def test_a_corrupt_line_in_the_spend_log_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._corrupted(DurableLedger(name=LocalCallSpendLog.LEDGER, row=CallSpendPayload).path())

        code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "not JSON" in output.err

    @staticmethod
    def _corrupted(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json\n", encoding="utf-8")

    def test_main_wires_the_parsed_arguments_into_spend(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())

        code = Cli.main(
            [
                "spend",
                "--repo",
                self._REPO,
                "--issue",
                str(self._ISSUE),
                "--slice",
                self._SLICE,
                "--step",
                str(Step.IMPLEMENT),
            ]
        )

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out)
        assert printed["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)

    def test_the_split_between_implementing_and_judging_is_answered_by_two_calls_with_no_subtraction_by_hand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._traced_and_spent(step=Step.IMPLEMENT, call=HarnessCallSpendMother.of_the_implementer())
        self._traced_and_spent(step=Step.VERIFY, call=HarnessCallSpendMother.of_the_judge())

        implementer_code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.IMPLEMENT)
        implementer_cost = json.loads(capsys.readouterr().out)["cost_usd"]
        judge_code = Cli.spend(repo=self._REPO, issue=self._ISSUE, slice_id=self._SLICE, step=Step.VERIFY)
        judge_cost = json.loads(capsys.readouterr().out)["cost_usd"]

        assert implementer_code == ExitCode.OK
        assert judge_code == ExitCode.OK
        assert implementer_cost == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert judge_cost == pytest.approx(HarnessSpendMother.of_the_judge_call().cost_usd)

    def test_the_slice_has_no_default_because_a_guessed_one_sums_the_wrong_calls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(
                ["spend", "--repo", "alcaptar/slice-runner", "--issue", "45", "--step", str(Step.IMPLEMENT)]
            )

        assert "the following arguments are required: --slice" in capsys.readouterr().err

    def test_a_step_nobody_declared_is_refused_instead_of_being_forwarded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["spend", "--slice", self._SLICE, "--step", "deploy"])

        assert "invalid choice" in capsys.readouterr().err


class TestTheCommandThatEmitsClosedSliceMetrics:
    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @staticmethod
    def _closed() -> None:
        LocalMetricsLog(clock=SystemClock()).record(ClosedSliceMother.merged())

    @staticmethod
    def _record(closed: ClosedSlice) -> None:
        LocalMetricsLog(clock=SystemClock()).record(closed)

    @staticmethod
    def _row_for(closed: ClosedSlice, *, issue: int) -> dict[str, object]:
        row = MetricsEntryPayload.from_domain(
            closed,
            ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat(),
        ).to_contract()
        row["issue"] = issue
        row["slice_id"] = f"slice-{issue}"
        return row

    @staticmethod
    def _append_row(row: dict[str, object]) -> None:
        ledger = DurableLedger(name=LocalMetricsLog.LEDGER, row=MetricsEntryPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(f"{json.dumps(row)}\n")

    @staticmethod
    def _emitted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
        code = Cli.metrics(
            repo=None,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=tmp_path / "view.html",
        )
        assert code == ExitCode.OK
        return capsys.readouterr().out.strip().splitlines()

    def test_a_closed_slice_is_printed_as_one_json_line_and_the_view_is_written_to_the_path_given(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()
        out = tmp_path / "view.html"

        code = Cli.metrics(
            repo=ClosedSliceMother.REPO,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=out,
        )

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out.strip().splitlines()[0])
        assert (printed["repo"], printed["slice_id"], printed["state"]) == (
            ClosedSliceMother.REPO,
            ClosedSliceMother.SLICE_ID,
            "merged",
        )
        assert out.exists()
        assert "slice-runner metrics" in out.read_text(encoding="utf-8")

    def test_a_window_with_nothing_closed_still_prints_the_summary_line_with_zero_samples(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = tmp_path / "view.html"

        code = Cli.metrics(
            repo=ClosedSliceMother.REPO,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=out,
        )

        assert code == ExitCode.OK
        summary = json.loads(capsys.readouterr().out.strip())
        assert summary["samples"] == 0
        assert summary["rates"]["first_attempt"] == {"samples": 0}
        assert out.exists()

    def test_the_verifier_fail_rate_counts_only_slices_the_judge_vetoed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.because_of(ClosingReason.JUDGE), issue=101))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=102))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["verifier_fail"] == {"value": 50.0, "samples": 2}

    def test_the_blocked_by_controls_rate_does_not_count_a_verifier_veto(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.because_of(ClosingReason.CONTROLS), issue=201))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.because_of(ClosingReason.JUDGE), issue=202))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=203))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["blocked_by_controls"] == {"value": 33.3, "samples": 3}

    def test_the_first_attempt_rate_excludes_a_slice_that_needed_a_retry_of_controls_or_ci(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_after_retrying_controls_and_ci(control_retries=1, ci_retries=0))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=ClosedSliceMother.ISSUE + 1))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["first_attempt"] == {"value": 50.0, "samples": 2}

    def test_the_implement_retries_rate_is_the_mean_of_every_way_back_to_that_step(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_after_retrying_controls_and_ci(control_retries=1, ci_retries=3))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=ClosedSliceMother.ISSUE + 1))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["implement_retries"] == {"value": 2.0, "samples": 2}

    def test_the_ci_red_rate_counts_only_slices_closed_with_a_red_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.because_of(ClosingReason.CI_RED), issue=301))
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=302))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["ci_red"] == {"value": 50.0, "samples": 2}

    def test_the_verify_discards_rate_counts_slices_where_the_judges_contract_broke_at_least_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_after_going_back_for_every_reason())
        self._record(ClosedSliceMother.closed_as_for_issue(Closure.merged(), issue=ClosedSliceMother.ISSUE + 1))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["rates"]["verify_discards"] == {"value": 50.0, "samples": 2}

    def test_a_record_declaring_two_models_is_counted_in_both_of_their_groups(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(
            ClosedSliceMother.merged_measuring(
                HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
            )
        )

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        labels = {group["label"] for group in summary["by_model"]}
        assert labels == {"claude-sonnet-5", "claude-haiku-4-5-20251001"}
        assert all(group["rates"]["first_attempt"]["samples"] == 1 for group in summary["by_model"])

    def test_a_row_declaring_no_model_is_grouped_as_unknown_instead_of_disappearing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_measuring_nothing())

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert {group["label"] for group in summary["by_model"]} == {"unknown"}

    def test_two_rows_with_different_declared_variants_land_in_their_own_group(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_for_issue(402))
        row = self._row_for(ClosedSliceMother.merged(), issue=403)
        row["variant"] = "skill"
        self._append_row(row)

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        samples_by_label = {
            group["label"]: group["rates"]["first_attempt"]["samples"] for group in summary["by_variant"]
        }
        assert samples_by_label == {MetricsEntryPayload.VARIANT: 1, "skill": 1}

    def test_the_spend_averages_only_count_the_records_that_measured_something(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_measuring(HarnessSpendMother.of_the_implementer_call()))
        self._append_row(self._row_for(ClosedSliceMother.merged_measuring_nothing(), issue=501))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert summary["spend"]["cost_usd"] == {
            "value": round(HarnessSpendMother.of_the_implementer_call().cost_usd, 2),
            "samples": 1,
        }

    def test_the_discards_by_cause_only_count_rows_that_declare_a_cause(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_a_failed_call()))
        self._append_row(
            self._row_for(
                ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_an_incoherent_verdict()),
                issue=601,
            )
        )
        self._append_row(self._row_for(ClosedSliceMother.merged(), issue=602))

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        tallies = {tally["cause"]: tally["count"] for tally in summary["discards_by_cause"]}
        assert tallies == {"failed-call": 1, "incoherent-verdict": 1, "no-structured-output": 0}
        assert all(tally["samples"] == 2 for tally in summary["discards_by_cause"])

    def test_a_discard_of_a_step_other_than_verify_does_not_count_as_a_verify_discard(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._record(ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_a_failed_call()))
        self._append_row(
            self._row_for(
                ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_the_step(Step.IMPLEMENT)),
                issue=701,
            )
        )

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        tallies = {tally["cause"]: tally["count"] for tally in summary["discards_by_cause"]}
        assert tallies["failed-call"] == 1
        assert all(tally["samples"] == 1 for tally in summary["discards_by_cause"])

    def test_the_summary_line_names_its_top_level_keys_literally(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()

        summary = json.loads(self._emitted(tmp_path, capsys)[-1])

        assert set(summary) == {"samples", "rates", "spend", "discards_by_cause", "by_model", "by_variant"}
        assert set(summary["rates"]) == {
            "verifier_fail",
            "blocked_by_controls",
            "first_attempt",
            "implement_retries",
            "verify_discards",
            "ci_red",
        }
        assert set(summary["spend"]) == {
            "cost_usd",
            "turns",
            "duration_ms",
            "cache_read_tokens",
            "input_tokens",
            "output_tokens",
        }

    def test_a_corrupt_line_in_the_call_trace_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()
        ledger = DurableLedger(name=LocalCallTrace.LEDGER, row=HarnessCallPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("not json\n", encoding="utf-8")

        code = Cli.metrics(
            repo=ClosedSliceMother.REPO,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=tmp_path / "view.html",
        )

        assert code == ExitCode.USAGE_ERROR
        assert "not JSON" in capsys.readouterr().err

    def test_a_corrupt_line_in_the_metrics_log_itself_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()
        ledger = DurableLedger(name=LocalMetricsLog.LEDGER, row=MetricsEntryPayload).path()
        ledger.write_text("not json\n", encoding="utf-8")

        code = Cli.metrics(
            repo=ClosedSliceMother.REPO,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=tmp_path / "view.html",
        )

        assert code == ExitCode.USAGE_ERROR
        assert "not JSON" in capsys.readouterr().err

    def test_main_wires_the_parsed_arguments_into_metrics(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()
        out = tmp_path / "view.html"

        code = Cli.main(
            [
                "metrics",
                "--repo",
                ClosedSliceMother.REPO,
                "--since",
                "2000-01-01",
                "--until",
                "2100-01-01",
                "--out",
                str(out),
            ]
        )

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out.strip().splitlines()[0])
        assert printed["repo"] == ClosedSliceMother.REPO
        assert out.exists()

    def test_without_since_and_until_every_closed_slice_up_to_now_is_included(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._closed()

        code = Cli.main(["metrics", "--repo", ClosedSliceMother.REPO, "--out", str(tmp_path / "view.html")])

        assert code == ExitCode.OK
        printed = json.loads(capsys.readouterr().out.strip().splitlines()[0])
        assert printed["repo"] == ClosedSliceMother.REPO

    def test_the_out_path_has_no_default_because_a_guessed_one_hides_the_view(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["metrics"])

        assert "the following arguments are required: --out" in capsys.readouterr().err

    def test_a_row_from_another_repo_of_an_earlier_generation_does_not_break_metrics_scoped_to_this_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._append_row({"repo": "another/repo", "issue": 1, "name": "old-shape"})
        self._closed()
        out = tmp_path / "view.html"

        code = Cli.metrics(
            repo=ClosedSliceMother.REPO,
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            out=out,
        )

        assert code == ExitCode.OK


class TestTheTransitionOfEveryPair:
    @pytest.mark.parametrize(("step", "outcome", "spent", "expected"), _TABLE)
    def test_every_pair_of_step_and_outcome_has_one_answer_and_this_is_it(
        self,
        step: Step,
        outcome: Outcome,
        spent: dict[str, int],
        expected: tuple[Step, Closure, int],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome, **spent), budgets=Budgets())

        assert code == ExitCode.OK
        emitted = json.loads(capsys.readouterr().out)
        assert (emitted["run"]["step"], emitted["state"], emitted["wait_seconds"]) == expected

    def test_the_whole_run_travels_in_the_transition_so_nobody_downstream_recounts_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED, verify_discards=1)

        Cli.explain(request=asked, budgets=Budgets())

        assert json.loads(capsys.readouterr().out) == {
            "run": {
                "step": "implement",
                "retry_instruction": "",
                "tree_unexpected": False,
                "previous_call_died": False,
                "catching_up_the_branch": False,
                "control_retries": 1,
                "hygiene_retries": 0,
                "verify_retries": 0,
                "ci_retries": 0,
                "catch_up_retries": 0,
                "indeterminate_ticks": 0,
                "verify_discards": 1,
                "implement_discards": 0,
                "control_rounds_logged": 1,
                "verify_rounds_logged": 0,
                "last_reviewed_id": 0,
                "requested_changes": [],
            },
            "state": "open",
            "wait_seconds": 0,
        }


class TestWhatEachBudgetPays:
    def test_a_red_control_spends_a_retry_of_its_own_and_not_one_of_the_judge(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.FAILED), budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["control_retries"], spent["verify_retries"]) == (1, 0)

    def test_a_control_that_could_not_run_spends_no_retry_at_all_unlike_a_red_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(
            request=TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.INDETERMINATE, control_retries=2),
            budgets=Budgets(),
        )

        emitted = json.loads(capsys.readouterr().out)
        assert emitted["state"] == "open"
        assert emitted["run"]["control_retries"] == 2

    def test_a_hygiene_rejection_spends_a_retry_of_its_own_and_not_one_of_the_controls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.RUN_CONTROLS, Outcome.HYGIENE_REJECTED)

        Cli.explain(request=asked, budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["hygiene_retries"], spent["control_retries"]) == (1, 0)

    def test_a_veto_spends_a_retry_of_the_judge_and_not_one_of_the_controls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(request=TransitionRequestMother.asking(Step.VERIFY, Outcome.FAILED), budgets=Budgets())

        spent = json.loads(capsys.readouterr().out)["run"]
        assert (spent["verify_retries"], spent["control_retries"]) == (1, 0)

    def test_a_discarded_verdict_is_counted_apart_because_the_code_was_never_touched(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli.explain(
            request=TransitionRequestMother.asking(Step.VERIFY, Outcome.DISCARDED, verify_retries=2),
            budgets=Budgets(),
        )

        emitted = json.loads(capsys.readouterr().out)
        assert emitted["state"] == "open"
        assert (emitted["run"]["verify_discards"], emitted["run"]["verify_retries"]) == (1, 2)

    def test_an_answer_from_the_ci_clears_the_ticks_that_had_none_because_the_window_wants_them_consecutive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.AWAIT_CI, Outcome.PENDING, indeterminate_ticks=2)

        Cli.explain(request=asked, budgets=Budgets())

        assert json.loads(capsys.readouterr().out)["run"]["indeterminate_ticks"] == 0


class TestWhenThereIsNoTransitionToExplain:
    @pytest.mark.parametrize(("step", "outcome"), _IMPOSSIBLE)
    def test_a_pair_the_prose_never_describes_is_refused_instead_of_taking_a_generic_branch(
        self, step: Step, outcome: Outcome, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.asking(step, outcome), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert f"`{step}`" in output.err
        assert f"`{outcome}`" in output.err

    def test_a_run_that_is_not_json_is_refused_because_a_guessed_one_advances_the_wrong_slice(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.not_even_json(), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        assert capsys.readouterr().out == ""

    def test_a_step_nobody_declared_is_refused_instead_of_defaulting_to_the_first_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_step_nobody_declared(), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        assert "deploy" in capsys.readouterr().err

    def test_a_counter_that_arrives_as_text_is_refused_because_it_decides_when_a_budget_runs_out(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.explain(request=TransitionRequestMother.with_a_counter_that_arrives_as_text(), budgets=Budgets())

        assert code == ExitCode.USAGE_ERROR
        assert "control_retries" in capsys.readouterr().err


class TestTheDocumentedCommand:
    def test_it_parses_with_the_repo_the_base_and_the_slice(self) -> None:
        arguments = Cli.parser().parse_args(
            ["verify", "--repo", "/repos/project", "--base", "master", "--slice", _SLICE]
        )

        assert (arguments.repo, arguments.base, arguments.slice_id) == ("/repos/project", "master", _SLICE)

    def test_the_base_has_no_default_value_because_a_guessed_one_diffs_the_wrong_range(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["verify", "--repo", "/repos/project", "--slice", _SLICE])

        assert "the following arguments are required: --base" in capsys.readouterr().err

    def test_the_slice_has_no_default_value_because_a_guessed_one_files_the_pair_under_the_wrong_slice(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["verify", "--repo", "/repos/project", "--base", "master"])

        assert "the following arguments are required: --slice" in capsys.readouterr().err

    def test_explain_takes_the_run_on_standard_input_and_not_as_a_flag(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.IMPLEMENT, Outcome.DONE)
        monkeypatch.setattr(sys, "stdin", io.StringIO(asked))

        code = Cli.main(["explain"])

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out)["run"]["step"] == Step.RUN_CONTROLS


class TestTheCommandThatConductsASlice:
    @staticmethod
    def _complete() -> list[str]:
        return [
            "run",
            str(GhConversationMother.ISSUE),
            "--repo",
            GhConversationMother.REPO,
            "--base",
            GhConversationMother.BASE,
        ]

    def test_it_parses_with_the_issue_as_a_positional_and_the_repo_of_the_issue_and_the_base_as_flags(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert (arguments.issue, arguments.repo, arguments.base) == (
            GhConversationMother.ISSUE,
            GhConversationMother.REPO,
            GhConversationMother.BASE,
        )

    def test_the_worktree_has_no_default_path_because_the_program_derives_and_mounts_its_own(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.worktree is None

    def test_the_root_of_the_clone_the_worktree_hangs_from_defaults_to_the_current_directory(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.repo_root == "."

    def test_both_the_worktree_and_the_root_of_the_clone_can_be_given_and_are_kept_apart(self) -> None:
        arguments = Cli.parser().parse_args(
            [*self._complete(), "--worktree", "/trees/by-hand", "--repo-root", "/clone"]
        )

        assert (arguments.worktree, arguments.repo_root) == ("/trees/by-hand", "/clone")

    def test_the_directory_of_the_control_logs_defaults_to_one_under_the_configuration_root_of_the_tool(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.logs == tmp_path / "slice-runner" / "runs" / "controls"

    def test_the_directory_of_the_control_logs_can_be_set_explicitly_and_it_overrides_the_default(
        self, tmp_path: Path
    ) -> None:
        arguments = Cli.parser().parse_args([*self._complete(), "--logs", str(tmp_path / "chosen")])

        assert arguments.logs == tmp_path / "chosen"

    def test_the_repo_of_the_issue_has_no_default_because_a_guessed_one_reads_another_issue(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", str(GhConversationMother.ISSUE), "--base", GhConversationMother.BASE])

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert "the following arguments are required: --repo" in output.err

    def test_the_base_has_no_default_because_a_guessed_one_opens_the_pull_request_against_the_wrong_branch(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", str(GhConversationMother.ISSUE), "--repo", GhConversationMother.REPO])

        assert code == ExitCode.USAGE_ERROR
        assert "the following arguments are required: --base" in capsys.readouterr().err

    def test_the_issue_is_read_as_a_number_so_a_word_is_refused_instead_of_searched_for(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", "the-loop", "--repo", GhConversationMother.REPO, "--base", GhConversationMother.BASE])

        assert code == ExitCode.USAGE_ERROR
        assert "the-loop" in capsys.readouterr().err

    def test_asking_for_the_help_of_the_subcommand_is_not_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["run", "--help"])

        assert code == ExitCode.OK
        assert "--worktree" in capsys.readouterr().out

    def test_the_slice_defaults_to_none_because_without_it_the_next_runnable_one_is_chosen(self) -> None:
        arguments = Cli.parser().parse_args(self._complete())

        assert arguments.slice_id is None

    def test_the_slice_can_be_named_explicitly_to_conduct_that_one_instead_of_the_next_in_line(self) -> None:
        arguments = Cli.parser().parse_args([*self._complete(), "--slice", _SLICE])

        assert arguments.slice_id == _SLICE


class TestConductingASliceAnEarlierInvocationLeftHalfDone:
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_merged_pull_request()),
            ),
        )

    def test_it_neither_implements_nor_stages_nor_runs_a_control_because_the_state_says_that_is_done(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert not invocation.process.invoked(ImplementerInvocation.EXECUTABLE)
        assert not invocation.process.invoked("git", "add")
        assert not invocation.process.invoked("sh", "-c", GhConversationMother.CONTROL)

    def test_it_asks_the_forum_for_the_merge_because_that_is_the_step_the_state_left_it_on(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("gh", "pr", "view", str(GhConversationMother.PULL_REQUEST))

    def test_what_it_emits_is_the_halt_the_state_and_the_step_the_run_stopped_on(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = self._invocation().conduct(logs=tmp_path / "logs")

        assert code == ExitCode.OK
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "merged",
            "step": "await-merge",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_the_directory_of_the_control_logs_is_made_because_a_control_writes_its_log_straight_into_it(
        self, tmp_path: Path
    ) -> None:
        logs = tmp_path / "logs"

        self._invocation().conduct(logs=logs)

        assert logs.is_dir()

    def test_the_run_leaves_its_transitions_in_the_ledger_without_a_status_and_the_last_one_is_merged(
        self, tmp_path: Path
    ) -> None:
        self._invocation().conduct(logs=tmp_path / "logs")

        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert ledger.name == "transitions.jsonl"
        assert all("status" not in row for row in rows)
        assert rows[-1]["standing"] == "merged"

    def test_the_transition_that_closes_the_run_is_reported_on_standard_error_leaving_the_result_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._invocation().conduct(logs=tmp_path / "logs")

        output = capsys.readouterr()
        reported = json.loads(output.err)
        assert (reported["step"], reported["standing"]) == ("await-merge", "merged")
        assert "status" not in reported
        assert json.loads(output.out)["halt"] == "run-closed"


class TestConductingTheSliceNamedByTheCaller:
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(RunMother.awaiting_merge()),
            parent=GhConversationMother.parent_of_two_slices(),
            mounted=False,
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_merged_pull_request()),
            ),
        )

    def test_the_slice_named_by_the_caller_is_conducted_instead_of_the_first_one_in_line(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", slice_id=GhConversationMother.OTHER_SLICE, worktree=None)

        assert invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.OTHER_BRANCH)
        assert not invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.BRANCH)

    def test_without_the_slice_argument_the_first_one_in_line_is_still_chosen(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", worktree=None)

        assert invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.BRANCH)
        assert not invocation.process.invoked("gh", "pr", "list", "--head", GhConversationMother.OTHER_BRANCH)


class TestAskingForASliceThatCannotBeRun:
    def test_a_slice_that_does_not_exist_among_the_issue_fails_closed_without_writing_anything(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(RunMother.awaiting_merge()),
            parent=GhConversationMother.parent_of_two_slices(),
        )

        code = invocation.conduct(logs=tmp_path / "logs", slice_id="slice-99")

        assert code == ExitCode.NO_SLICE_LEFT
        assert "slice-99" in capsys.readouterr().err
        assert not invocation.process.invoked("gh", "issue", "edit")
        assert not invocation.process.invoked("gh", "issue", "comment")
        assert not invocation.process.invoked("gh", "pr", "list")

    def test_a_slice_that_is_not_runnable_fails_closed_the_same_way_as_one_that_does_not_exist(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.two_slices_resumed_at(
                RunMother.awaiting_merge(), second_label=IssueLabel.BLOCKED_JUDGE
            ),
            parent=GhConversationMother.parent_of_two_slices(),
            answers=(Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),),
        )

        code = invocation.conduct(logs=tmp_path / "logs", slice_id=GhConversationMother.OTHER_SLICE, worktree=None)

        assert code == ExitCode.NO_SLICE_LEFT
        assert GhConversationMother.OTHER_SLICE in capsys.readouterr().err
        assert not invocation.process.invoked("gh", "issue", "edit")
        assert not invocation.process.invoked("gh", "pr", "list")


class TestWhenTheRunClosesWithoutBeingMerged:
    def test_a_ci_in_red_with_no_retry_left_exits_with_its_own_code_because_the_issue_has_to_be_looked_at(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.with_the_only_ci_retry_already_spent()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "blocked-ci-red",
            "step": "await-ci",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_a_pull_request_in_conflict_with_no_checks_closes_on_the_first_tick_without_waiting_for_the_window(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.about_to_ask_the_ci()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "checks"), stdout="[]"),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_in_conflict_with_its_base()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(catch_up_retries=0))

        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "blocked-ci-conflict",
            "step": "await-ci",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_a_branch_taken_by_another_worktree_closes_with_the_code_of_every_unmerged_run_and_names_the_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            answers=(
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", worktree="/trees/by-hand")

        captured = capsys.readouterr()
        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(captured.out) == {"halt": "run-closed", "state": "blocked-worktree", "step": "mount-worktree"}
        assert GhConversationMother.WORKTREE in captured.err
        assert not invocation.process.invoked("git", "worktree", "add")


class TestTheModelsTheClosedRunRecords(WithTheDurableStoresOutOfTheRealHome):
    def test_the_metrics_row_of_a_closure_carries_the_full_model_identifiers_the_entrypoint_wires(
        self, tmp_path: Path
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.with_the_only_ci_retry_already_spent()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
            ),
        )

        invocation.conduct(logs=tmp_path / "logs")

        rows = (tmp_path / "slice-runner" / "runs" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(rows[-1])["models_by_role"] == {
            "implement": "claude-sonnet-5-5",
            "verify": "claude-opus-5-5",
        }

    def test_the_metrics_row_of_a_closure_carries_the_effort_the_entrypoint_wires_for_each_role(
        self, tmp_path: Path
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.with_the_only_ci_retry_already_spent()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
            ),
        )

        invocation.conduct(logs=tmp_path / "logs")

        rows = (tmp_path / "slice-runner" / "runs" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(rows[-1])["effort_by_role"] == {"implement": "high", "verify": "high"}


class TestRetiringTheWorktreeFromTheCommandLine:
    @staticmethod
    def _merging(*, status: str = "", removing: bool = True) -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_merged_pull_request()),
                Answer(to=("git", "status", "--porcelain"), stdout=status),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                *((Answer(to=("git", "worktree", "remove")), Answer(to=("git", "branch", "-D"))) if removing else ()),
            ),
        )

    def test_a_merged_run_that_mounted_its_own_worktree_asks_git_to_remove_it_and_its_branch(
        self, tmp_path: Path
    ) -> None:
        invocation = self._merging()

        code = invocation.conduct(logs=tmp_path / "logs", worktree=None)

        assert code == ExitCode.OK
        assert invocation.process.invoked("git", "worktree", "remove", GhConversationMother.WORKTREE)
        assert invocation.process.invoked("git", "branch", "-D", GhConversationMother.BRANCH)

    def test_a_merged_run_with_work_left_in_its_worktree_keeps_it_says_where_and_still_exits_as_merged(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = self._merging(status=" M src/module.py\n", removing=False)

        code = invocation.conduct(logs=tmp_path / "logs", worktree=None)

        captured = capsys.readouterr()
        assert code == ExitCode.OK
        assert json.loads(captured.out)["state"] == "merged"
        assert not invocation.process.invoked("git", "worktree", "remove")
        assert GhConversationMother.WORKTREE in captured.err
        assert "kept-uncommitted-work" in captured.err

    def test_a_tree_left_by_an_earlier_run_closes_the_invocation_with_the_command_to_resolve_it_by_hand(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(replace(RunMother.implementing(), tree_unexpected=True)),
            answers=(
                Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", worktree=None)

        captured = capsys.readouterr()
        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(captured.out)["state"] == "blocked-worktree"
        assert f"git worktree remove {GhConversationMother.WORKTREE}" in captured.err
        assert not invocation.process.invoked("git", "worktree", "add")

    def test_a_tree_left_by_a_run_that_persisted_nothing_is_written_down_as_unexpected_so_a_retry_blocks_on_it_again(
        self, tmp_path: Path
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_marked_in_progress_that_never_persisted_a_run(),
            answers=(
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

        invocation.conduct(logs=tmp_path / "logs", worktree=None)

        written = [
            call.stdin for call in invocation.process.calls if "edit" in call.argv and "--body-file" in call.argv
        ]
        assert '"tree_unexpected": true' in written[-1]

    def test_a_tree_left_by_a_run_that_persisted_nothing_closes_the_invocation_with_the_command_to_resolve_it_by_hand(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_marked_in_progress_that_never_persisted_a_run(),
            answers=(
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", worktree=None)

        captured = capsys.readouterr()
        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(captured.out)["state"] == "blocked-worktree"
        assert f"git worktree remove {GhConversationMother.WORKTREE}" in captured.err
        assert not invocation.process.invoked("git", "worktree", "add")


class TestTheRoundTripAfterARedCiThatStillHasARetryLeft(BlindToTheToolboxOfThisMachine):
    @classmethod
    def _invocation(cls) -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.about_to_ask_the_ci()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "list", "--state", "open"), stdout=GhConversationMother.the_open_pull_request()),
                Answer(to=("gh", "pr", "checks"), stdout=GhConversationMother.checks_in_red()),
                Answer(
                    to=("gh", "issue", "view", "--json", "comments"),
                    stdout=json.dumps({"comments": []}),
                ),
                Answer(
                    to=(ImplementerInvocation.EXECUTABLE, "bypassPermissions"),
                    stdout=json.dumps(HarnessEnvelopeMother.recorded(_IMPLEMENTER_PAYLOAD)),
                ),
                Answer(to=("git", "add")),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout=cls._what_the_implementer_left_staged()),
                Answer(to=("sh", "-c", GhConversationMother.CONTROL)),
                Answer(to=("git", "diff", "--cached", "--numstat"), stdout="1\t0\thello.py\n1\t0\ttest_hello.py\n"),
                Answer(to=("git", "diff", "--cached"), stdout="diff --git a/hello.py b/hello.py\n"),
                Answer(
                    to=(JudgeInvocation.EXECUTABLE, "--add-dir"),
                    stdout=json.dumps(HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing())),
                ),
                Answer(to=("git", "symbolic-ref"), stdout=f"{GhConversationMother.BRANCH}\n"),
                Answer(to=("git", "commit")),
                Answer(to=("git", "push")),
            ),
        )

    @staticmethod
    def _what_the_implementer_left_staged() -> str:
        return "hello.py\ntest_hello.py\n"

    def test_the_slice_is_implemented_again_and_walks_the_whole_loop_back_to_the_ci(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = self._invocation()

        code = invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked(ImplementerInvocation.EXECUTABLE, "bypassPermissions")
        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out) == {
            "halt": "run-closed",
            "state": "blocked-ci-red",
            "step": "await-ci",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }

    def test_the_code_written_to_fix_the_red_ci_is_committed_and_pushed_so_it_reaches_the_remote(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("git", "commit")
        assert invocation.process.invoked("git", "push", GhConversationMother.BRANCH)

    def test_the_branch_that_already_carries_its_pull_request_is_not_given_a_second_one(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked("gh", "pr", "list", "--state", "open")
        assert not invocation.process.invoked("gh", "pr", "create")


class TestTheControlLogsOfARetriedRound(BlindToTheToolboxOfThisMachine):
    @staticmethod
    def _invocation(run: Run) -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(run),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("git", "fetch"), code=0),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),
                Answer(
                    to=(ImplementerInvocation.EXECUTABLE, "bypassPermissions"),
                    stdout=json.dumps(HarnessEnvelopeMother.recorded(_IMPLEMENTER_PAYLOAD)),
                ),
                Answer(to=("git", "add")),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout="hello.py\ntest_hello.py\n"),
                Answer(to=("sh", "-c", GhConversationMother.CONTROL), code=1, stdout="lint failed"),
            ),
        )

    @staticmethod
    def _slice_dir(logs: Path, *, issue: int = GhConversationMother.ISSUE) -> Path:
        return logs / GhConversationMother.REPO / str(issue) / GhConversationMother.SLICE

    def test_two_retried_rounds_of_the_same_slice_both_keep_their_log_on_disk(self, tmp_path: Path) -> None:
        invocation = self._invocation(RunMother.implementing())

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(control_retries=1))

        slice_dir = self._slice_dir(tmp_path / "logs")
        assert (slice_dir / "round-1" / "lint.log").exists()
        assert (slice_dir / "round-2" / "lint.log").exists()

    def test_a_round_counted_in_the_written_state_is_read_back_so_the_next_one_is_not_named_round_one(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation(RunMother.implementing_with_one_round_already_logged())

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(control_retries=0))

        slice_dir = self._slice_dir(tmp_path / "logs")
        assert (slice_dir / "round-2" / "lint.log").exists()
        assert not (slice_dir / "round-1").exists()

    def test_two_features_sharing_the_same_slice_identifier_do_not_overwrite_each_other_s_log(
        self, tmp_path: Path
    ) -> None:
        logs = tmp_path / "logs"
        first_issue, second_issue = GhConversationMother.ISSUE, GhConversationMother.ISSUE + 1

        self._invocation(RunMother.implementing()).conduct(
            logs=logs, budgets=Budgets(control_retries=0), issue=first_issue
        )
        self._invocation(RunMother.implementing()).conduct(
            logs=logs, budgets=Budgets(control_retries=0), issue=second_issue
        )

        assert (self._slice_dir(logs, issue=first_issue) / "round-1" / "lint.log").exists()
        assert (self._slice_dir(logs, issue=second_issue) / "round-1" / "lint.log").exists()


class TestWhenTheImplementerLeavesTheDiffUntouched(BlindToTheToolboxOfThisMachine):
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.judging()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("git", "fetch"), code=0),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "issue", "view", "--json", "comments"), stdout=json.dumps({"comments": []})),
                Answer(
                    to=(ImplementerInvocation.EXECUTABLE, "bypassPermissions"),
                    stdout=json.dumps(HarnessEnvelopeMother.recorded(_IMPLEMENTER_PAYLOAD)),
                ),
                Answer(to=("git", "add")),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout="hello.py\ntest_hello.py\n"),
                Answer(to=("sh", "-c", GhConversationMother.CONTROL)),
                Answer(to=("git", "diff", "--cached", "--numstat"), stdout="1\t0\thello.py\n1\t0\ttest_hello.py\n"),
                Answer(to=("git", "diff", "--cached"), stdout="diff --git a/hello.py b/hello.py\n"),
                Answer(
                    to=(JudgeInvocation.EXECUTABLE, "--add-dir"),
                    stdout=json.dumps(HarnessEnvelopeMother.carrying(JudgeVerdictMother.failing())),
                ),
                Answer(to=("git", "push")),
            ),
        )

    @staticmethod
    def _verdicts_under(tmp_path: Path) -> list[dict[str, object]]:
        ledger = tmp_path / "no-toolbox" / "slice-runner" / "runs" / "verdicts.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    def test_the_second_round_with_the_same_diff_never_launches_the_process_of_the_judge(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=1))

        assert invocation.process.times_invoked(JudgeInvocation.EXECUTABLE, "--add-dir") == 1

    def test_the_run_closes_naming_that_nothing_moved_with_an_exit_code_that_is_not_the_one_of_a_veto(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = self._invocation()

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=1))

        assert code == ExitCode.RUN_UNMERGED
        assert json.loads(capsys.readouterr().out)["state"] == "blocked-verify"
        labels = [
            Argv(call.argv).value_of("--add-label") for call in invocation.process.calls if "--add-label" in call.argv
        ]
        assert labels[-1] == IssueLabel.BLOCKED_JUDGE

    def test_the_round_that_was_not_judged_leaves_no_row_in_the_corpus(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=1))

        assert [entry["verify_round"] for entry in self._verdicts_under(tmp_path)] == [1]

    def test_the_comment_that_closes_the_run_carries_what_the_judge_still_demands(self, tmp_path: Path) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=1))

        comments = [call.stdin for call in invocation.process.calls if call.argv[:3] == ["gh", "issue", "comment"]]
        published = next(body for body in comments if VetoFindingsComment.is_the_veto_findings(body))
        assert "Hallazgos vigentes tras la ultima ronda" in published

    def test_a_diff_that_changes_in_a_byte_is_judged_again(self, tmp_path: Path) -> None:
        invocation = self._invocation()
        invocation.process = AnsweringByArgvWithADiffThatMoves.over(
            invocation.process,
            diffs=("diff --git a/hello.py b/hello.py\n+return 2\n", "diff --git a/hello.py b/hello.py\n+return 3\n"),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=1))

        assert invocation.process.times_invoked(JudgeInvocation.EXECUTABLE, "--add-dir") == 2
        assert code == ExitCode.RUN_UNMERGED

    def test_the_first_round_of_a_slice_is_judged_because_there_is_nothing_to_compare_with(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=0))

        assert invocation.process.times_invoked(JudgeInvocation.EXECUTABLE, "--add-dir") == 1
        assert [entry["verify_round"] for entry in self._verdicts_under(tmp_path)] == [1]


class TestTheVerifyRoundOfARetriedVerdict(BlindToTheToolboxOfThisMachine):
    @staticmethod
    def _invocation() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(
                RunMother.judging_with_one_verify_round_already_logged()
            ),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("git", "fetch"), code=0),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout="hello.py\n"),
                Answer(to=("git", "diff", "--cached", "--numstat"), stdout="1\t0\thello.py\n"),
                Answer(to=("git", "diff", "--cached"), stdout="diff --git a/hello.py b/hello.py\n"),
                Answer(
                    to=(JudgeInvocation.EXECUTABLE, "--add-dir"),
                    stdout=json.dumps(HarnessEnvelopeMother.carrying(JudgeVerdictMother.failing())),
                ),
            ),
        )

    def test_a_round_already_counted_in_the_resumed_state_is_read_back_so_the_verdict_is_not_recorded_as_round_one(
        self, tmp_path: Path
    ) -> None:
        invocation = self._invocation()

        invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(verify_retries=0))

        ledger = tmp_path / "no-toolbox" / "slice-runner" / "runs" / "verdicts.jsonl"
        recorded = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert [entry["verify_round"] for entry in recorded] == [2]


class TestWhenTheRunStaysOpen:
    @staticmethod
    def _never_run() -> RunInvocation:
        return RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            mounted=False,
            answers=(
                Answer(to=("git", "fetch", "origin")),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
                Answer(to=(ImplementerInvocation.EXECUTABLE, "bypassPermissions"), stdout="not an envelope"),
            ),
        )

    def test_the_branch_and_the_worktree_of_the_slice_are_cut_from_the_base_the_invocation_named(
        self, tmp_path: Path
    ) -> None:
        invocation = self._never_run()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.ran(
            "git",
            "-C",
            GhConversationMother.ROOT,
            "worktree",
            "add",
            "-b",
            GhConversationMother.BRANCH,
            GhConversationMother.WORKTREE,
            f"origin/{GhConversationMother.BASE}",
        )

    def test_a_slice_that_was_never_run_goes_from_mounting_to_the_implementer_without_asking_for_an_understanding(
        self, tmp_path: Path
    ) -> None:
        invocation = self._never_run()

        invocation.conduct(logs=tmp_path / "logs")

        assert invocation.process.invoked(ImplementerInvocation.EXECUTABLE, "bypassPermissions")

    def test_a_precheck_that_is_not_clear_exits_with_its_own_code_and_names_which_one_stopped_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            mounted=False,
            answers=(
                Answer(to=("git", "fetch", "origin")),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.the_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        assert json.loads(capsys.readouterr().out)["precheck"] == "pull-request-already-open"

    def test_a_parent_without_decisions_stops_the_run_before_any_worktree_is_mounted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            parent=GhConversationMother.parent_of_one_slice_without_decisions(),
            mounted=False,
            answers=self._clear_ground(),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        assert json.loads(capsys.readouterr().out)["precheck"] == "missing-decisions"
        assert not invocation.process.invoked("git", "worktree", "add")

    def test_a_subissue_without_decisions_stops_the_run_before_any_worktree_is_mounted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run_without_decisions(),
            mounted=False,
            answers=self._clear_ground(),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        assert json.loads(capsys.readouterr().out)["precheck"] == "missing-decisions"
        assert not invocation.process.invoked("git", "worktree", "add")

    @staticmethod
    def _clear_ground() -> tuple[Answer, ...]:
        return (
            Answer(to=("git", "fetch", "origin")),
            Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
            Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
        )

    def test_a_base_that_does_not_resolve_against_its_remote_exits_with_its_own_precheck_and_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            mounted=False,
            answers=(
                Answer(to=("git", "fetch", "origin")),
                Answer(
                    to=("git", "rev-list", "--count"),
                    code=128,
                    stderr=f"fatal: ambiguous argument '{GhConversationMother.BASE}..origin/"
                    f"{GhConversationMother.BASE}'",
                ),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        assert json.loads(capsys.readouterr().out)["precheck"] == "base-not-on-remote"
        assert not invocation.process.invoked("gh", "issue", "edit")
        assert not invocation.process.invoked("git", "worktree", "add")

    def test_an_unreadable_declared_source_exits_naming_the_path_and_the_motive_and_leaves_them_on_the_subissue(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            mounted=False,
            answers=(
                Answer(to=("git", "fetch", "origin")),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
                Answer(to=("cat", "CLAUDE.md"), code=1, stderr="cat: CLAUDE.md: No such file or directory"),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PRECHECKS_BLOCKED
        reported = json.loads(capsys.readouterr().out)
        assert reported["precheck"] == "unreadable-source"
        assert "CLAUDE.md" in reported["precheck_reason"]
        comment = next(call for call in invocation.process.calls if call.argv[:3] == ["gh", "issue", "comment"])
        assert "unreadable-source" in comment.stdin
        assert "CLAUDE.md" in comment.stdin

    def test_declared_sources_over_the_size_budget_exit_naming_each_one_and_its_weight_and_leave_it_on_the_subissue(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_never_run(),
            mounted=False,
            answers=(
                Answer(to=("git", "fetch", "origin")),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
                Answer(to=("cat", "CLAUDE.md"), stdout="a" * 11),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(sources_max_chars=10))

        assert code == ExitCode.PRECHECKS_BLOCKED
        reported = json.loads(capsys.readouterr().out)
        assert reported["precheck"] == "sources-over-budget"
        assert "CLAUDE.md: 11 characters" in reported["precheck_reason"]
        comment = next(call for call in invocation.process.calls if call.argv[:3] == ["gh", "issue", "comment"])
        assert "sources-over-budget" in comment.stdin
        assert "CLAUDE.md: 11 characters" in comment.stdin

    def test_a_merge_that_never_arrives_spends_the_whole_wait_and_says_the_pull_request_is_still_draft(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_still_open()),
                Answer(
                    to=(f"repos/{GhConversationMother.REPO}/pulls/{GhConversationMother.PULL_REQUEST}/reviews",),
                    stdout="[]",
                ),
                Answer(
                    to=(f"repos/{GhConversationMother.REPO}/pulls/{GhConversationMother.PULL_REQUEST}/comments",),
                    stdout="[]",
                ),
                Answer(to=("gh", "issue", "comment")),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")
        captured = capsys.readouterr()

        assert code == ExitCode.WAIT_EXHAUSTED
        assert sum(slept) == Budgets().person_wait_seconds
        assert json.loads(captured.out)["halt"] == "wait-exhausted"
        assert invocation.process.invoked("gh", "issue", "comment")
        assert "draft" in captured.err
        assert str(GhConversationMother.PULL_REQUEST) in captured.err

    def test_a_pull_request_closed_without_merging_ends_the_invocation_with_its_own_code_and_no_waiting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_closed_without_merging()),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.PULL_REQUEST_CLOSED
        assert slept == []
        assert json.loads(capsys.readouterr().out) == {
            "halt": "pull-request-closed",
            "state": "open",
            "step": "await-merge",
            "pull_request": GhConversationMother.PULL_REQUEST,
        }


class TestWhenTheInvocationCannotBeConducted(ReadingWhatWasReported):
    def test_an_issue_whose_slices_are_all_closed_exits_saying_there_is_nothing_left_to_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(children=GhConversationMother.the_slice_already_closed())

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.NO_SLICE_LEFT
        assert str(GhConversationMother.ISSUE) in self._reported(capsys)

    def test_a_subissue_titled_as_no_slice_is_a_usage_error_and_not_a_run_that_went_wrong(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(children=GhConversationMother.a_title_that_names_no_slice())

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.USAGE_ERROR
        assert "slice-NN" in self._reported(capsys)

    @pytest.mark.parametrize(
        ("retired", "replacement"),
        [
            ("bloqueada:higiene", "bloqueada:controles"),
            ("bloqueada:verify", "bloqueada:juez"),
            ("bloqueada:sin-cambios", "bloqueada:juez"),
            ("bloqueada:worktree-sin-retirar", "bloqueada:worktree"),
        ],
    )
    def test_a_subissue_carrying_a_retired_label_is_refused_naming_the_retired_label_and_the_one_that_replaced_it(
        self, retired: str, replacement: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        children = GhConversationMother.the_slice_resumed_at(
            RunMother.blocked_on_controls(), label=RetiredIssueLabel(retired)
        )
        invocation = RunInvocation(children=children)

        code = invocation.conduct(logs=tmp_path / "logs")

        reported = self._reported(capsys)
        assert code == ExitCode.USAGE_ERROR
        assert retired in reported
        assert replacement in reported
        assert not invocation.process.invoked("git", "worktree", "add")

    def test_a_gh_that_fails_mid_run_exits_with_the_code_of_an_interrupted_run_carrying_what_it_said(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("gh", "pr", "list", "--state", "all"), code=1, stderr="gh: authentication required"),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs")

        assert code == ExitCode.RUN_INTERRUPTED
        assert "authentication required" in self._reported(capsys)


class TestWhenACallOutlivesItsCap(ReadingWhatWasReported):
    def test_conducting_a_slice_exits_with_the_code_of_the_cap_and_not_with_the_one_that_says_to_reinvoke(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=TimingOutProcess(), budgets=Budgets()).run(RunInvocation.params(logs=tmp_path / "logs"))

        assert code == ExitCode.PROCESS_TIMED_OUT
        assert "gh: killed after 1s" in self._reported(capsys)

    def test_verifying_a_slice_exits_with_the_code_of_the_cap_and_not_with_the_one_of_a_missing_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=TimingOutProcess(), budgets=Budgets()).verify(
            repo=str(tmp_path), base=VerifyProcessMother.BASE, slice_id=_SLICE
        )

        assert code == ExitCode.PROCESS_TIMED_OUT
        assert "git: killed after 1s" in self._reported(capsys)


class TestWhenDeclaredSourcesAreOverBudget(ReadingWhatWasReported):
    def test_conducting_a_slice_stops_with_the_code_of_the_budget_instead_of_sending_a_prompt(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.judging()),
            answers=(
                Answer(to=("cat", "CLAUDE.md"), stdout="a" * 11),
                Answer(to=("git", "rev-parse"), code=0),
                Answer(to=("git", "fetch"), code=0),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("git", "diff", "--cached", "--name-only"), stdout="hello.py\n"),
                Answer(to=("git", "diff", "--cached", "--numstat"), stdout="1\t0\thello.py\n"),
                Answer(to=("git", "diff", "--cached"), stdout="diff --git a/hello.py b/hello.py\n"),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(sources_max_chars=10))

        assert code == ExitCode.SOURCES_BUDGET_EXCEEDED
        assert "the declared sources are over the budget" in self._reported(capsys)
        assert not invocation.process.invoked(JudgeInvocation.EXECUTABLE)


class TestTheBudgetsTheEntrypointInjects:
    def test_a_conducted_run_waits_the_budget_the_entrypoint_was_given_and_not_one_of_its_own(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[int] = []
        monkeypatch.setattr("time.sleep", slept.append)
        invocation = RunInvocation(
            children=GhConversationMother.the_slice_resumed_at(RunMother.awaiting_merge()),
            answers=(
                Answer(to=("git", "rev-parse"), code=0),
                Answer(
                    to=("gh", "pr", "list", "--state", "all"),
                    stdout=GhConversationMother.the_pull_request_of_the_branch(),
                ),
                Answer(to=("gh", "pr", "view"), stdout=GhConversationMother.a_pull_request_still_open()),
                Answer(
                    to=(f"repos/{GhConversationMother.REPO}/pulls/{GhConversationMother.PULL_REQUEST}/reviews",),
                    stdout="[]",
                ),
                Answer(
                    to=(f"repos/{GhConversationMother.REPO}/pulls/{GhConversationMother.PULL_REQUEST}/comments",),
                    stdout="[]",
                ),
            ),
        )

        code = invocation.conduct(logs=tmp_path / "logs", budgets=Budgets(person_wait_seconds=60))

        assert code == ExitCode.WAIT_EXHAUSTED
        assert sum(slept) == 60

    def test_an_explained_transition_ticks_at_the_cadence_the_entrypoint_was_given_and_not_at_one_of_its_own(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        asked = TransitionRequestMother.asking(Step.AWAIT_CI, Outcome.PENDING)

        Cli.explain(request=asked, budgets=Budgets(seconds_between_ticks=7))

        assert json.loads(capsys.readouterr().out)["wait_seconds"] == 7


class TestTheCommandThatChecksReadiness:
    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        (tmp_path / "skills" / "slice-spec").mkdir(parents=True)
        (tmp_path / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"superpowers@claude-plugins-official": True}}), encoding="utf-8"
        )

    @staticmethod
    def _process(
        *,
        authenticated: bool = True,
        repo_readable: bool = True,
        commits_behind: int = 0,
        base_resolves: bool = True,
    ) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer(to=("git", "--version"), stdout="git version 2.51.0\n"),
            Answer(to=("gh", "--version"), stdout="gh version 2.55.0\n"),
            Answer(to=("claude", "--version"), stdout="2.1.4\n"),
            Answer(to=("gh", "api", "user"), stdout="someone\n")
            if authenticated
            else Answer(to=("gh", "api", "user"), code=1, stderr="gh: not logged in"),
            Answer(to=("gh", "repo", "view"), stdout=json.dumps({"name": "slice-runner"}))
            if repo_readable
            else Answer(to=("gh", "repo", "view"), code=1, stderr="GraphQL: Could not resolve to a Repository"),
            Answer(to=("git", "fetch", "origin"), stdout=""),
            Answer(to=("git", "rev-list", "--count"), stdout=f"{commits_behind}\n")
            if base_resolves
            else Answer(
                to=("git", "rev-list", "--count"),
                code=128,
                stderr="fatal: ambiguous argument 'master..origin/master': unknown revision or path not in the "
                "working tree.",
            ),
        )

    def test_with_everything_ready_it_exits_with_zero(self) -> None:
        code = Cli(process=self._process(), budgets=Budgets()).doctor()

        assert code == ExitCode.OK

    def test_every_check_is_named_in_what_is_printed(self, capsys: pytest.CaptureFixture[str]) -> None:
        Cli(process=self._process(), budgets=Budgets()).doctor()

        printed = capsys.readouterr().out
        for name in (
            "git",
            "gh",
            "claude",
            "skill slice-spec",
            "plugin superpowers",
            "version",
        ):
            assert name in printed

    def test_the_version_line_carries_the_version_of_the_installed_package(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli(process=self._process(), budgets=Budgets()).doctor()

        lines = capsys.readouterr().out.splitlines()
        version_line = next(line for line in lines if line.split()[1] == "version")
        assert version_line.endswith(metadata.version("slice-runner"))

    def test_nothing_about_the_checkout_the_program_came_from_is_printed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli(process=self._process(), budgets=Budgets()).doctor()

        printed = capsys.readouterr().out
        for name in ("provenance", "installed code", "checkout upstream"):
            assert name not in printed

    def test_it_asks_nothing_of_the_process_to_know_which_code_is_installed(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).doctor()

        assert not any(call.argv[:2] == ["diff", "-rq"] for call in process.calls)
        assert not any(call.argv[-2:] == ["--count", "HEAD..@{upstream}"] for call in process.calls)

    def test_something_missing_exits_with_its_own_code_distinct_from_a_usage_error(self) -> None:
        code = Cli(process=self._process(authenticated=False), budgets=Budgets()).doctor()

        assert code == ExitCode.ENVIRONMENT_NOT_READY
        assert code != ExitCode.USAGE_ERROR

    def test_a_missing_check_prints_the_command_that_fixes_it(self, capsys: pytest.CaptureFixture[str]) -> None:
        Cli(process=self._process(authenticated=False), budgets=Budgets()).doctor()

        assert "gh auth login" in capsys.readouterr().out

    def test_the_doctor_never_runs_the_fix_it_prints(self) -> None:
        process = self._process(authenticated=False)

        Cli(process=process, budgets=Budgets()).doctor()

        assert not process.invoked("gh", "auth", "login")

    def test_claude_is_only_asked_for_its_version_and_never_invoked_for_real(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).doctor()

        assert process.ran("claude", "--version")
        assert not process.invoked("claude", "-p")

    def test_it_parses_with_no_argument_at_all(self) -> None:
        arguments = Cli.parser().parse_args(["doctor"])

        assert arguments.command == "doctor"
        assert arguments.repo is None
        assert arguments.worktree is None
        assert arguments.base is None

    def test_it_parses_repo_worktree_and_base_when_given(self) -> None:
        arguments = Cli.parser().parse_args(
            ["doctor", "--repo", "alcaptar/slice-runner", "--worktree", "/repos/slice-runner", "--base", "master"]
        )

        assert arguments.repo == "alcaptar/slice-runner"
        assert arguments.worktree == "/repos/slice-runner"
        assert arguments.base == "master"

    def test_with_a_readable_repo_the_repo_check_is_named_in_what_is_printed_and_it_stays_ready(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=self._process(repo_readable=True), budgets=Budgets()).doctor(repo="alcaptar/slice-runner")

        assert code == ExitCode.OK
        assert "repo" in capsys.readouterr().out

    def test_with_an_unreadable_repo_it_exits_with_the_not_ready_code(self) -> None:
        code = Cli(process=self._process(repo_readable=False), budgets=Budgets()).doctor(repo="alcaptar/slice-runner")

        assert code == ExitCode.ENVIRONMENT_NOT_READY

    def test_with_a_base_up_to_date_with_its_remote_the_base_check_is_named_and_it_stays_ready(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=self._process(commits_behind=0), budgets=Budgets()).doctor(
            worktree="/repos/slice-runner", base="master"
        )

        assert code == ExitCode.OK
        assert "base" in capsys.readouterr().out

    def test_a_base_lagging_behind_its_remote_still_exits_with_zero_because_a_warning_is_not_a_failure(self) -> None:
        code = Cli(process=self._process(commits_behind=3), budgets=Budgets()).doctor(
            worktree="/repos/slice-runner", base="master"
        )

        assert code == ExitCode.OK

    def test_a_lagging_base_prints_the_command_that_brings_it_up_to_date(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Cli(process=self._process(commits_behind=3), budgets=Budgets()).doctor(
            worktree="/repos/slice-runner", base="master"
        )

        printed = capsys.readouterr().out
        assert "master" in printed
        assert "origin/master" in printed

    def test_the_doctor_never_runs_the_command_that_would_update_the_lagging_base(self) -> None:
        process = self._process(commits_behind=3)

        Cli(process=process, budgets=Budgets()).doctor(worktree="/repos/slice-runner", base="master")

        assert not process.invoked("branch", "-f")

    def test_without_worktree_or_base_neither_is_asked_about_and_behaviour_stays_as_before(self) -> None:
        code = Cli(process=self._process(), budgets=Budgets()).doctor()

        assert code == ExitCode.OK

    def test_a_base_that_does_not_resolve_against_its_remote_exits_with_the_not_ready_code_naming_the_base(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=self._process(base_resolves=False), budgets=Budgets()).doctor(
            worktree="/repos/slice-runner", base="master"
        )

        assert code == ExitCode.ENVIRONMENT_NOT_READY
        assert code != ExitCode.RUN_INTERRUPTED
        assert "master" in capsys.readouterr().out

    def test_main_wires_the_doctor_subcommand_over_the_process_it_builds(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        EntrypointProcess.answering_with(monkeypatch, self._process(authenticated=False))

        code = Cli.main(["doctor"])

        assert code == ExitCode.ENVIRONMENT_NOT_READY
        printed = capsys.readouterr().out
        assert "ready" in printed
        assert "missing" in printed


class TestTheCommandThatResetsASlice:
    _REPO = "alcaptar/slice-runner"
    _ISSUE = 50

    @classmethod
    def _process(cls, *, view: dict[str, object] | None = None) -> AnsweringByArgv:
        payload = view if view is not None else GhResponseMother.children_of_parent()[0]
        body = payload["body"]
        assert isinstance(body, str)

        return AnsweringByArgv(
            Answer(to=("view", "--json", "number,title,body,labels,state"), stdout=json.dumps(payload)),
            Answer(to=("view", "--json", "body"), stdout=json.dumps({"body": body})),
            Answer(to=("edit", "--body-file")),
            Answer(to=("edit", "--add-label")),
            Answer(to=("comment",)),
        )

    def test_it_exits_with_zero_and_declares_the_branch_and_the_working_tree_untouched(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli(process=self._process(), budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.OK
        printed = capsys.readouterr().out
        assert "slice/01-primera-de-prueba" in printed
        assert "untouched" in printed

    def test_the_label_write_removes_the_blocking_label_and_adds_pending(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        edit = next(call for call in process.calls if "--add-label" in call.argv)
        assert Argv(edit.argv).value_of("--add-label") == "estado:pendiente"
        assert Argv(edit.argv).value_of("--remove-label") == "estado:en-curso"

    def test_the_execution_state_block_is_gone_from_the_body_it_writes_back(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        rewritten = next(call for call in process.calls if "--body-file" in call.argv)
        assert "slice-runner:estado" not in rewritten.stdin

    def test_a_comment_is_left_marking_the_reset(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        comment = next(call for call in process.calls if "comment" in call.argv)
        assert ResetComment.MARKER in comment.stdin

    def test_a_subissue_with_no_recognizable_spec_is_rejected_as_a_usage_error_writing_nothing(self) -> None:
        bodiless = {"number": self._ISSUE, "title": "slice-01 (x): y", "body": "", "labels": [], "state": "OPEN"}
        process = self._process(view=bodiless)

        code = Cli(process=process, budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.USAGE_ERROR
        assert len(process.calls) == 1

    def test_a_response_gh_cannot_read_is_reported_as_a_usage_error(self) -> None:
        process = AnsweringByArgv(Answer(to=("view",), stdout="not json"))

        code = Cli(process=process, budgets=Budgets()).reset(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.USAGE_ERROR


class TheFeatureBeingShown:
    _REPO = "alcaptar/slice-runner"
    _ISSUE = 38

    @classmethod
    def _process(
        cls, *, children: list[dict[str, object]] | None = None, pull_requests: list[dict[str, object]] | None = None
    ) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer(
                to=("view", "--json", "body,subIssuesSummary,state"),
                stdout=json.dumps(GhResponseMother.parent_with_two_children()),
            ),
            Answer(
                to=("issue", "list", "--json", "number,title,body,labels,state"),
                stdout=json.dumps(children if children is not None else GhResponseMother.children_of_parent()),
            ),
            Answer(
                to=("pr", "list", "--json", "number,headRefName"),
                stdout=json.dumps(pull_requests or []),
            ),
        )

    @staticmethod
    def _labelled(*, number: int, title: str, label: str) -> dict[str, object]:
        return {
            "body": "INTENCION: x\nACEPTACION: y\nSENAL: exenta - x\n",
            "labels": [{"id": str(number), "name": label, "description": "", "color": "000000"}],
            "number": number,
            "state": "OPEN",
            "title": title,
        }


class TestTheCommandThatShowsFeatureStatus(TheFeatureBeingShown):
    def test_it_exits_with_zero_and_prints_one_line_per_slice(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.OK
        printed = capsys.readouterr().out
        lines = printed.strip().splitlines()
        assert len(lines) == 2
        assert any("slice-01" in line for line in lines)
        assert any("slice-02" in line for line in lines)

    def test_a_slice_with_a_run_shows_the_step_it_is_on(self, capsys: pytest.CaptureFixture[str]) -> None:
        Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        lines = capsys.readouterr().out.strip().splitlines()
        slice_01 = next(line for line in lines if "slice-01" in line)
        assert Step.AWAIT_CI.value in slice_01

    def test_a_slice_that_never_started_shows_no_step_at_all(self, capsys: pytest.CaptureFixture[str]) -> None:
        Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        lines = capsys.readouterr().out.strip().splitlines()
        slice_02 = next(line for line in lines if "slice-02" in line)
        assert not any(step.value in slice_02 for step in Step)

    def test_the_pull_request_of_a_branch_is_shown_next_to_its_own_slice_only(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pull_requests = [{"number": 47, "headRefName": "slice/01-primera-de-prueba"}]

        Cli(process=self._process(pull_requests=pull_requests), budgets=Budgets()).status(
            repo=self._REPO, issue=self._ISSUE
        )

        lines = capsys.readouterr().out.strip().splitlines()
        slice_01 = next(line for line in lines if "slice-01" in line)
        slice_02 = next(line for line in lines if "slice-02" in line)
        assert "47" in slice_01
        assert "47" not in slice_02

    def test_it_never_writes_anything_gh_only_ever_reads(self) -> None:
        process = self._process()

        Cli(process=process, budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        assert not any(token in call.argv for call in process.calls for token in ("edit", "comment", "create", "label"))

    def test_a_feature_with_a_blocked_and_an_aborted_slice_still_exits_with_zero(self) -> None:
        children = [
            self._labelled(number=50, title="slice-01 (x): y", label=IssueLabel.BLOCKED_CI_RED.value),
            self._labelled(number=51, title="slice-02 (x): y", label=IssueLabel.ABORTED_BUDGET.value),
        ]

        code = Cli(process=self._process(children=children), budgets=Budgets()).status(
            repo=self._REPO, issue=self._ISSUE
        )

        assert code == ExitCode.OK

    def test_a_response_gh_cannot_read_is_reported_on_standard_error_and_not_on_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = AnsweringByArgv(Answer(to=("view",), stdout="not json"))

        code = Cli(process=process, budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err != ""

    def test_a_closed_slice_without_a_run_shows_its_closure_state_and_cost_from_the_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        LocalMetricsLog(clock=SystemClock()).record(ClosedSliceMother.merged_for_issue(49))

        Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        lines = capsys.readouterr().out.strip().splitlines()
        slice_02 = next(line for line in lines if "slice-02" in line)
        assert "merged" in slice_02
        assert "$" in slice_02

    def test_a_corrupt_line_in_the_metrics_log_exits_with_a_usage_error_instead_of_a_stack_dump(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ledger = DurableLedger(name=LocalMetricsLog.LEDGER, row=MetricsEntryPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("not json\n", encoding="utf-8")

        code = Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.USAGE_ERROR
        assert "not JSON" in capsys.readouterr().err

    def test_a_row_of_an_earlier_generation_belonging_to_an_issue_outside_this_feature_does_not_break_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ledger = DurableLedger(name=LocalMetricsLog.LEDGER, row=MetricsEntryPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(f"{json.dumps({'repo': self._REPO, 'issue': 999, 'name': 'old-shape'})}\n")

        code = Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE)

        assert code == ExitCode.OK
        assert capsys.readouterr().err == ""


class TestTheCommandThatShowsFeatureStatusAsJson(TheFeatureBeingShown):
    @pytest.fixture(autouse=True)
    def toolbox(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @staticmethod
    def _printed(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
        return [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    @classmethod
    def _printed_by(
        cls,
        capsys: pytest.CaptureFixture[str],
        *,
        children: list[dict[str, object]] | None = None,
        pull_requests: list[dict[str, object]] | None = None,
    ) -> dict[str, dict[str, object]]:
        process = cls._process(children=children, pull_requests=pull_requests)
        Cli(process=process, budgets=Budgets()).status(repo=cls._REPO, issue=cls._ISSUE, as_json=True)

        return {str(line["slice_id"]): line for line in cls._printed(capsys)}

    def test_it_exits_with_zero_and_prints_one_json_line_per_slice(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = Cli(process=self._process(), budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE, as_json=True)

        assert code == ExitCode.OK
        assert [line["slice_id"] for line in self._printed(capsys)] == ["slice-01", "slice-02"]

    def test_a_slice_that_never_ran_still_says_who_it_is_and_that_it_is_open(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        printed = self._printed_by(capsys)

        slice_02 = printed["slice-02"]
        assert slice_02["version"] == 1
        assert slice_02["name"] == "segunda-de-prueba"
        assert slice_02["issue"] == 49
        assert slice_02["closed"] is False
        assert "cost_usd" not in slice_02
        assert "pull_request" not in slice_02

    def test_the_pull_request_of_a_branch_is_in_its_own_slice_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        pull_requests = [{"number": 47, "headRefName": "slice/01-primera-de-prueba"}]

        printed = self._printed_by(capsys, pull_requests=pull_requests)

        assert printed["slice-01"]["pull_request"] == 47
        assert "pull_request" not in printed["slice-02"]

    def test_a_closed_subissue_is_reported_as_closed_and_an_open_one_as_open(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        printed = self._printed_by(capsys)

        assert (printed["slice-01"]["closed"], printed["slice-02"]["closed"]) == (True, False)

    def test_each_slice_carries_the_label_of_its_state(self, capsys: pytest.CaptureFixture[str]) -> None:
        printed = self._printed_by(capsys)

        assert printed["slice-01"]["label"] == IssueLabel.IN_PROGRESS.value
        assert printed["slice-02"]["label"] == IssueLabel.PENDING.value

    def test_a_slice_with_a_run_carries_the_cost_measured_in_its_calls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        coordinates = SliceCoordinates(repo=self._REPO, issue=50, slice_id=CanonicalSliceId.of_text("slice-01"))
        call = HarnessCallSpend(
            coordinates=coordinates,
            session=HarnessEnvelopeMother.SESSION_OF_THE_IMPLEMENTER,
            spend=HarnessSpendMother.of_the_implementer_call(),
        )
        LocalCallSpendLog(clock=SystemClock()).record(call)

        printed = self._printed_by(capsys)

        assert printed["slice-01"]["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert "cost_usd" not in printed["slice-02"]

    def test_a_slice_without_a_run_carries_the_cost_its_closure_left_in_the_registry(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalMetricsLog(clock=SystemClock()).record(ClosedSliceMother.merged_for_issue(49))

        printed = self._printed_by(capsys)

        assert printed["slice-02"]["cost_usd"] == pytest.approx(HarnessSpendMother.of_the_implementer_call().cost_usd)
        assert "cost_usd" not in printed["slice-01"]

    def test_a_response_gh_cannot_read_writes_nothing_on_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = AnsweringByArgv(Answer(to=("view",), stdout="not json"))

        code = Cli(process=process, budgets=Budgets()).status(repo=self._REPO, issue=self._ISSUE, as_json=True)

        assert code == ExitCode.USAGE_ERROR
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err != ""


class TestTheStatusCommandParsing:
    def test_it_parses_with_the_issue_as_a_positional_and_the_repo_as_a_flag(self) -> None:
        arguments = Cli.parser().parse_args(["status", "38", "--repo", "alcaptar/slice-runner"])

        assert (arguments.issue, arguments.repo) == (38, "alcaptar/slice-runner")

    def test_json_is_off_unless_asked_for(self) -> None:
        plain = Cli.parser().parse_args(["status", "38", "--repo", "alcaptar/slice-runner"])
        asked = Cli.parser().parse_args(["status", "38", "--repo", "alcaptar/slice-runner", "--json"])

        assert (plain.json, asked.json) == (False, True)

    def test_the_repo_has_no_default_because_a_guessed_one_reads_another_issue(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["status", "38"])

        assert "the following arguments are required: --repo" in capsys.readouterr().err


class TestTheCommandThatFollowsTheEventsAsJson(WithTheEntrypointLaunchingNothing, WithTheDurableStoresOutOfTheRealHome):
    _ROUNDS: ClassVar[dict[str, object]] = {
        "controls": {"used": 0, "limit": 2},
        "hygiene": {"used": 0, "limit": 2},
        "judge": {"used": 0, "limit": 2},
        "ci": {"used": 0, "limit": 1},
        "ci_indeterminate": {"used": 0, "limit": 10},
        "catch_up": {"used": 0, "limit": 3},
    }
    _ADVANCING: ClassVar[dict[str, object]] = {
        "version": 2,
        "kind": "transition",
        "ts": 1704112245000,
        "repo": EventMother.REPO,
        "issue": EventMother.ISSUE,
        "parent": FeatureSliceMother.PARENT,
        "slice_id": "slice-05",
        "name": FeatureSliceMother.NAME,
        "standing": "in-progress",
        "step": "run-controls",
        "rounds": _ROUNDS,
        "cost_usd": 0.3433209,
        "budget_usd": 50.0,
    }
    _MERGED: ClassVar[dict[str, object]] = {
        "version": 2,
        "kind": "transition",
        "ts": 1704112275000,
        "repo": EventMother.REPO,
        "issue": EventMother.ISSUE,
        "parent": FeatureSliceMother.PARENT,
        "slice_id": "slice-05",
        "name": FeatureSliceMother.NAME,
        "standing": "merged",
        "step": "await-merge",
        "rounds": _ROUNDS,
        "cost_usd": 0.051877,
        "budget_usd": 50.0,
    }

    @staticmethod
    def _cli() -> Cli:
        return Cli(process=ProcessDoubles.exiting(), budgets=Budgets())

    @staticmethod
    def _clock_interrupted_after(sleeps: int) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.sleep.side_effect = [None] * (sleeps - 1) + [KeyboardInterrupt()]

        return clock

    @staticmethod
    def _printed(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
        return [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    def test_it_prints_the_history_and_then_one_json_object_per_change_without_ending(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(EventMother.closed(),), cursor=EventCursor(offset=20)),
        )

        code = self._cli().follow(
            repo=None, once=False, as_json=True, reader=reader, clock=self._clock_interrupted_after(2)
        )

        assert code == ExitCode.OK
        assert self._printed(capsys) == [self._ADVANCING, self._MERGED]
        assert reader.cursors == [EventCursor.start(), EventCursor(offset=10)]

    def test_once_prints_the_history_of_the_first_read_as_json_and_never_sleeps(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(EventMother.closed(),), cursor=EventCursor(offset=20)),
        )
        clock = self._clock_interrupted_after(1)

        code = self._cli().follow(repo=None, once=True, as_json=True, reader=reader, clock=clock)

        assert code == ExitCode.OK
        assert self._printed(capsys) == [self._ADVANCING]
        clock.sleep.assert_not_called()
        assert len(reader.cursors) == 1

    def test_the_first_read_as_json_prints_every_transition_of_a_slice_so_its_history_can_be_told(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(), EventMother.closed()), cursor=EventCursor(offset=20))
        )

        self._cli().follow(repo=None, once=True, as_json=True, reader=reader, clock=self._clock_interrupted_after(1))

        assert self._printed(capsys) == [self._ADVANCING, self._MERGED]

    def test_the_first_read_as_json_ends_each_slice_with_its_latest_event_even_when_it_repeats_the_state(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        resumed = replace(EventMother.advancing(), pid=4242)
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(), resumed), cursor=EventCursor(offset=20))
        )

        self._cli().follow(repo=None, once=True, as_json=True, reader=reader, clock=self._clock_interrupted_after(1))

        printed = self._printed(capsys)
        assert len(printed) == 2
        assert printed[-1]["pid"] == 4242

    def test_a_row_written_before_the_feature_was_recorded_prints_without_the_parent_and_the_name(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing_before_the_feature_was_recorded(),), cursor=EventCursor(offset=10))
        )

        self._cli().follow(repo=None, once=True, as_json=True, reader=reader, clock=self._clock_interrupted_after(1))

        printed = self._printed(capsys)
        assert "parent" not in printed[0]
        assert "name" not in printed[0]
        assert printed[0]["version"] == 2

    def test_main_with_the_json_flag_reads_the_real_ledger_and_prints_objects(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalEventLog().emit(EventMother.advancing())
        capsys.readouterr()

        code = Cli.main(["follow", "--once", "--json"])

        assert code == ExitCode.OK
        assert self._printed(capsys) == [self._ADVANCING]


class TestTheCommandThatFollowsTheEvents(WithTheEntrypointLaunchingNothing, WithTheDurableStoresOutOfTheRealHome):
    _ADVANCING_LINE = "2024-01-01T12:30:45+00:00 alcaptar/slice-runner #150 slice-05 run-controls in-progress $0.34"
    _WAITING_LINE = "2024-01-01T12:31:45+00:00 alcaptar/slice-runner #150 slice-05 await-ci in-progress $0.34"
    _PENDING_LINE = "2024-01-01T12:30:45+00:00 alcaptar/slice-runner #150 slice-05 - pending $0.00"
    _MERGED_LINE = "2024-01-01T12:31:15+00:00 alcaptar/slice-runner #150 slice-05 await-merge merged $0.05"
    _BLOCKED_LINE = "2024-01-01T12:31:15+00:00 alcaptar/slice-runner #150 slice-05 await-merge blocked judge $0.05"

    @staticmethod
    def _clock_interrupted_after(sleeps: int) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.sleep.side_effect = [None] * (sleeps - 1) + [KeyboardInterrupt()]

        return clock

    @staticmethod
    def _cli(*, budgets: Budgets | None = None, process: Mock | None = None) -> Cli:
        return Cli(
            process=process if process is not None else ProcessDoubles.exiting(),
            budgets=budgets if budgets is not None else Budgets(),
        )

    def test_it_prints_the_snapshot_and_then_one_line_per_change_of_the_following_reads(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(
                events=(EventMother.advancing_again(minutes_later=1), EventMother.waiting_on_a_machine()),
                cursor=EventCursor(offset=30),
            ),
        )

        code = self._cli().follow(repo=None, once=False, reader=reader, clock=self._clock_interrupted_after(2))

        assert code == ExitCode.OK
        assert capsys.readouterr().out.splitlines() == [self._ADVANCING_LINE, self._WAITING_LINE]
        assert reader.cursors == [EventCursor.start(), EventCursor(offset=10)]

    def test_the_snapshot_shows_the_state_the_run_closed_with(self, capsys: pytest.CaptureFixture[str]) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.blocked_by_the_judge(),), cursor=EventCursor(offset=10))
        )

        self._cli().follow(repo=None, once=True, reader=reader, clock=self._clock_interrupted_after(1))

        assert capsys.readouterr().out.splitlines() == [self._BLOCKED_LINE]

    def test_the_line_of_the_change_to_closed_shows_the_state_the_run_closed_with(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(EventMother.closed(),), cursor=EventCursor(offset=20)),
        )

        self._cli().follow(repo=None, once=False, reader=reader, clock=self._clock_interrupted_after(2))

        assert capsys.readouterr().out.splitlines() == [self._ADVANCING_LINE, self._MERGED_LINE]

    def test_a_pending_row_is_printed_with_no_step_and_the_pending_standing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(EventBatch(events=(EventMother.pending(),), cursor=EventCursor(offset=10)))

        self._cli().follow(repo=None, once=True, reader=reader, clock=self._clock_interrupted_after(1))

        assert capsys.readouterr().out.splitlines() == [self._PENDING_LINE]

    def test_the_text_never_prints_a_value_of_the_retired_status_vocabulary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(EventMother.advancing(), EventMother.pending(), EventMother.round_without_changes()),
                cursor=EventCursor(offset=10),
            )
        )

        self._cli().follow(repo=None, once=True, reader=reader, clock=self._clock_interrupted_after(1))

        retired = {"advancing", "waiting", "awaiting-person", "closed", "nothing-to-commit"}
        assert retired.isdisjoint(capsys.readouterr().out.split())

    def test_a_row_repeating_the_step_and_closure_of_the_snapshot_prints_nothing_after_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(EventMother.advancing_again(minutes_later=1),), cursor=EventCursor(offset=20)),
        )

        self._cli().follow(repo=None, once=False, reader=reader, clock=self._clock_interrupted_after(2))

        assert capsys.readouterr().out.splitlines() == [self._ADVANCING_LINE]

    def test_once_prints_only_the_snapshot_exits_with_zero_and_never_sleeps(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(EventMother.advancing(), EventMother.waiting_on_a_machine()), cursor=EventCursor(offset=10)
            )
        )
        clock = self._clock_interrupted_after(1)

        code = self._cli().follow(repo=None, once=True, reader=reader, clock=clock)

        assert code == ExitCode.OK
        assert capsys.readouterr().out.splitlines() == [self._WAITING_LINE]
        clock.sleep.assert_not_called()
        assert len(reader.cursors) == 1

    def test_the_interval_between_reads_is_the_budget_and_not_a_literal_of_the_command(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(), cursor=EventCursor.start()), EventBatch(events=(), cursor=EventCursor.start())
        )
        clock = self._clock_interrupted_after(2)
        budgets = replace(Budgets(), seconds_between_follow_reads=Budgets().seconds_between_follow_reads + 3)

        self._cli(budgets=budgets).follow(repo=None, once=False, reader=reader, clock=clock)

        assert [call.kwargs for call in clock.sleep.call_args_list] == [
            {"seconds": budgets.seconds_between_follow_reads}
        ] * 2

    def test_following_launches_no_external_process(self) -> None:
        process = ProcessDoubles.exiting()
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)),
            EventBatch(events=(), cursor=EventCursor(offset=10)),
        )

        self._cli(process=process).follow(repo=None, once=False, reader=reader, clock=self._clock_interrupted_after(2))

        process.run.assert_not_called()

    def test_main_reads_the_real_ledger_and_the_repo_flag_keeps_only_that_repo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        log.emit(EventMother.advancing_in_another_repo())
        capsys.readouterr()

        code = Cli.main(["follow", "--once", "--repo", EventMother.ANOTHER_REPO])

        assert code == ExitCode.OK
        assert capsys.readouterr().out.splitlines() == [
            f"2024-01-01T12:30:45+00:00 {EventMother.ANOTHER_REPO} #150 slice-05 run-controls in-progress $0.34"
        ]

    def test_main_without_the_repo_flag_prints_every_repo(self, capsys: pytest.CaptureFixture[str]) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        log.emit(EventMother.advancing_in_another_repo())
        capsys.readouterr()

        Cli.main(["follow", "--once"])

        assert len(capsys.readouterr().out.splitlines()) == 2

    def test_a_ledger_line_this_generation_did_not_write_exits_with_a_usage_error_and_prints_nothing_to_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        LocalEventLog().emit(EventMother.advancing())
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write("not json\n")
        capsys.readouterr()

        code = Cli.main(["follow", "--once"])

        output = capsys.readouterr()
        assert code == ExitCode.USAGE_ERROR
        assert output.out == ""
        assert "not JSON" in output.err


class TestACommentTypedOnTheSubissueChangesNothingInTheNextRun:
    WRITING_COMMANDS: ClassVar[tuple[list[str], ...]] = (["issue", "edit"], ["issue", "comment"])

    @staticmethod
    def _blocked(typed: str | None) -> RunInvocation:
        return TestACommentTypedOnTheSubissueChangesNothingInTheNextRun._with(
            children=GhConversationMother.the_slice_aborted_before_touching_code(), typed=typed
        )

    @staticmethod
    def _with(*, children: str, typed: str | None) -> RunInvocation:
        comments = [] if typed is None else [typed]

        return RunInvocation(
            children=children,
            answers=(
                Answer(
                    to=("gh", "issue", "view", "comments"),
                    stdout=json.dumps({"comments": [{"body": body} for body in comments]}),
                ),
                Answer(to=("git", "rev-list", "--count"), stdout="0\n"),
                Answer(to=("gh", "pr", "list"), stdout=GhConversationMother.no_open_pull_request()),
            ),
        )

    @classmethod
    def _outcome(
        cls, invocation: RunInvocation, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> tuple[int, list[tuple[list[str], str]]]:
        code = invocation.conduct(logs=tmp_path / "logs")
        capsys.readouterr()
        writes = [
            (call.argv, call.stdin) for call in invocation.process.calls if call.argv[1:3] in cls.WRITING_COMMANDS
        ]

        return code, writes

    def test_a_retry_typed_on_a_blocked_slice_leaves_the_same_label_state_block_and_exit_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        without = self._outcome(self._blocked(None), tmp_path / "without", capsys)

        with_the_comment = self._outcome(self._blocked("-RETRY ya esta resuelto a mano"), tmp_path / "with", capsys)

        assert with_the_comment == without


class TestOpeningTheInterface:
    def test_the_process_is_replaced_by_the_interface_executable_without_any_argument(self) -> None:
        replacement = RecordedReplacement()

        with pytest.raises(ReplacementRequestedError):
            Cli.tui(replacement=replacement, issue=None)

        assert replacement.argvs == [["slice-runner-tui"]]

    def test_the_issue_number_travels_as_the_interface_argument(self) -> None:
        replacement = RecordedReplacement()

        with pytest.raises(ReplacementRequestedError):
            Cli.tui(replacement=replacement, issue=516)

        assert replacement.argvs == [["slice-runner-tui", "516"]]

    @pytest.mark.parametrize(
        ("arguments", "argv"),
        [(["tui"], ["slice-runner-tui"]), (["tui", "516"], ["slice-runner-tui", "516"])],
        ids=["without an issue", "with an issue"],
    )
    def test_the_subcommand_replaces_the_process_without_launching_any_process_first(
        self, monkeypatch: pytest.MonkeyPatch, arguments: list[str], argv: list[str]
    ) -> None:
        replacement = RecordedReplacement()
        process = ProcessDoubles.exiting()
        monkeypatch.setattr("slice_runner.infrastructure.cli.OsProcessReplacement", lambda: replacement)
        EntrypointProcess.answering_with(monkeypatch, process)

        Cli.main(arguments)

        assert replacement.argvs == [argv]
        assert process.run.mock_calls == []


class TestOpeningTheInterfaceWhenItIsNotInstalled(ReadingWhatWasReported):
    def test_it_exits_with_its_own_code_and_names_the_target_that_installs_it(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.tui(replacement=MissingExecutableReplacement(), issue=None)

        assert code == ExitCode.TUI_NOT_INSTALLED
        reported = self._reported(capsys)
        assert "slice-runner-tui" in reported
        assert "slice-runner update" in reported
        assert "make install" not in reported

    def test_the_subcommand_exits_with_the_code_when_the_replacement_finds_no_executable(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("slice_runner.infrastructure.cli.OsProcessReplacement", MissingExecutableReplacement)
        EntrypointProcess.answering_with(monkeypatch, AnsweringByArgv())

        code = Cli.main(["tui"])

        assert code == ExitCode.TUI_NOT_INSTALLED
        assert "slice-runner update" in self._reported(capsys)


class TestTheVersionTheProgramReports:
    def test_it_prints_the_version_the_installed_package_metadata_declares_and_exits_with_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main(["--version"])

        assert code == ExitCode.OK
        assert capsys.readouterr().out == f"{metadata.version('slice-runner')}\n"

    def test_it_is_the_version_pyproject_declares(self, capsys: pytest.CaptureFixture[str]) -> None:
        pyproject = Path(__file__).resolve().parents[4] / "pyproject.toml"
        declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

        Cli.main(["--version"])

        assert capsys.readouterr().out == f"{declared}\n"

    def test_it_prints_whatever_the_package_metadata_says_and_not_a_literal(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(metadata, "version", lambda distribution: "9.8.7")

        Cli.main(["--version"])

        assert capsys.readouterr().out == "9.8.7\n"
