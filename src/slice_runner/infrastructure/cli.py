from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.actions.catch_up_branch import CatchUpBranch
from slice_runner.application.actions.close_parent import CloseParent
from slice_runner.application.actions.commit_round import CommitRound
from slice_runner.application.actions.conduct_slice import (
    ConductSlice,
    ConductSliceParams,
    ConductSlicePorts,
    ConductSliceUseCases,
)
from slice_runner.application.actions.deliver_slice import DeliverSlice
from slice_runner.application.actions.implement_slice import ImplementSlice
from slice_runner.application.actions.mount_comparison import MountComparison
from slice_runner.application.actions.mount_worktree import MountWorktree
from slice_runner.application.actions.record_closure import RecordClosure
from slice_runner.application.actions.record_start import RecordStart
from slice_runner.application.actions.record_step import RecordStep
from slice_runner.application.actions.register_pending_slices import RegisterPendingSlices, RegisterPendingSlicesParams
from slice_runner.application.actions.reopen_slice import ReopenSlice, ReopenSliceParams
from slice_runner.application.actions.rescue_staged_work import RescueStagedWork
from slice_runner.application.actions.reset_slice import ResetSlice, ResetSliceParams
from slice_runner.application.actions.retire_worktree import RetireWorktree
from slice_runner.application.actions.run_controls import RunControls
from slice_runner.application.actions.stage_slice import StageSlice
from slice_runner.application.actions.update_program import (
    ReleaseIncomplete,
    UpdateCompleted,
    UpdateProgram,
    WheelInstalled,
)
from slice_runner.application.actions.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams, CheckReadinessPorts
from slice_runner.application.queries.check_sources import CheckSources
from slice_runner.application.queries.follow_activity import FollowActivity, FollowActivityParams
from slice_runner.application.queries.follow_events import FollowEvents, FollowEventsParams
from slice_runner.application.queries.list_closed_slices import ListClosedSlices, ListClosedSlicesParams
from slice_runner.application.queries.read_ci_status import ReadCiStatus
from slice_runner.application.queries.read_conversation import ReadConversation, ReadConversationParams
from slice_runner.application.queries.read_design_captures import ReadDesignCaptures
from slice_runner.application.queries.read_newer_release import ReadNewerRelease, ReadNewerReleaseParams
from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatus
from slice_runner.application.queries.run_prechecks import RunPrechecks
from slice_runner.application.queries.select_slice import SelectSlice
from slice_runner.application.queries.show_feature_status import ShowFeatureStatus, ShowFeatureStatusParams
from slice_runner.application.queries.spend_by_role import SpendByRole, SpendByRoleParams
from slice_runner.application.queries.spend_of_step import SpendOfStep, SpendOfStepParams
from slice_runner.domain.activity_cursors import ActivityCursors
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closed_slice_metrics import ClosedSliceMetrics
from slice_runner.domain.closed_slice_scope import ClosedSliceScope
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.exceptions import (
    BranchMismatchError,
    ConversationNotFoundError,
    DiffNotReadableError,
    ImpossibleTransitionError,
    InvalidHarnessOutputError,
    LaggingSearchIndexError,
    LiveRunsError,
    MalformedSliceIdError,
    MeasuredCallError,
    NoConversationRecordedError,
    NoPullRequestError,
    NoRecognizableSpecError,
    NoSliceLeftError,
    OrderRefusedError,
    ProtectedBranchError,
    RunNotClosedError,
    SourcesBudgetExceededError,
    UnreadableActivityLogError,
    UnreadableCallSpendLogError,
    UnreadableCallTraceError,
    UnreadableConversationError,
    UnreadableEventLogError,
    UnreadableForumError,
    UnreadableIssueError,
    UnreadableMetricsLogError,
    UnreadableRunError,
    UnresolvableRepoOrBaseError,
    UnsupportedPlatformError,
)
from slice_runner.domain.gh_retry_policy import GhRetryPolicy
from slice_runner.domain.halt import Halt
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.step import Step
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.infrastructure.activity_follow_json_report import ActivityFollowJsonReport
from slice_runner.infrastructure.branches_without_catch_up import BranchesWithoutCatchUp
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.closed_slice_metrics_payload import ClosedSliceMetricsPayload
from slice_runner.infrastructure.closed_slice_metrics_view import ClosedSliceMetricsView
from slice_runner.infrastructure.closed_slice_record_payload import ClosedSliceRecordPayload
from slice_runner.infrastructure.conducted_slice_payload import ConductedSlicePayload
from slice_runner.infrastructure.control_candidate_discovery import ControlCandidateDiscovery
from slice_runner.infrastructure.control_logs_directory import ControlLogsDirectory
from slice_runner.infrastructure.convention_source_discovery import ConventionSourceDiscovery
from slice_runner.infrastructure.conversation_report import ConversationReport
from slice_runner.infrastructure.conversation_tool_use_recorder import ConversationToolUseRecorder
from slice_runner.infrastructure.event_follow_json_report import EventFollowJsonReport
from slice_runner.infrastructure.event_follow_report import EventFollowReport
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.feature_status_json_report import FeatureStatusJsonReport
from slice_runner.infrastructure.feature_status_report import FeatureStatusReport
from slice_runner.infrastructure.gh_call import GhCall
from slice_runner.infrastructure.gh_child_issues import GhChildIssues
from slice_runner.infrastructure.gh_ci import GhCi
from slice_runner.infrastructure.gh_forum import GhForum
from slice_runner.infrastructure.gh_program_releases import GhProgramReleases
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError, GhRunRepository
from slice_runner.infrastructure.git_branches import GitBranches
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.git_diff_reader import GitDiffReader
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.infrastructure.git_worktrees import GitWorktrees
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.installed_version import InstalledVersion
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.kept_worktree_comment import KeptWorktreeComment
from slice_runner.infrastructure.local_activity_log import LocalActivityLog
from slice_runner.infrastructure.local_activity_reader import LocalActivityReader
from slice_runner.infrastructure.local_call_spend_log import LocalCallSpendLog
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.infrastructure.local_control_runner import LocalControlRunner
from slice_runner.infrastructure.local_conversation_log import LocalConversationLog
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.infrastructure.local_debt_ledger import LocalDebtLedger
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.infrastructure.local_event_reader import LocalEventReader
from slice_runner.infrastructure.local_host_platform import LocalHostPlatform
from slice_runner.infrastructure.local_metrics_log import LocalMetricsLog
from slice_runner.infrastructure.local_plugin_registry import LocalPluginRegistry
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.infrastructure.local_toolbox import LocalToolbox
from slice_runner.infrastructure.os_process_replacement import OsProcessReplacement
from slice_runner.infrastructure.pgrep_live_runs import PgrepLiveRuns
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError
from slice_runner.infrastructure.process_comparison_pages import ProcessComparisonPages
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.infrastructure.process_replacement import ExecutableNotFoundError
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.infrastructure.readiness_report import ReadinessReport
from slice_runner.infrastructure.slice_pull_request import SlicePullRequest
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stderr_turn_log import StderrTurnLog
from slice_runner.infrastructure.subcommand import Subcommand
from slice_runner.infrastructure.system_clock import SystemClock
from slice_runner.infrastructure.transition_payload import TransitionPayload
from slice_runner.infrastructure.transition_request_payload import TransitionRequestPayload
from slice_runner.infrastructure.uv_program_installation import UvProgramInstallation
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult
    from slice_runner.application.queries.follow_events import FollowEventsResult
    from slice_runner.domain.activity_reader import ActivityReader
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.event import Event
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.event_reader import EventReader
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.process_replacement import ProcessReplacement


class Cli:
    PROGRAM: ClassVar[str] = "slice-runner"
    TUI_EXECUTABLE: ClassVar[str] = "slice-runner-tui"
    CHECK_TIMEOUT_SECONDS: ClassVar[int] = 5
    RELEASES_REPO: ClassVar[str] = "alcaptar/slice-runner"
    PACKAGED_SKILLS: ClassVar[Path] = Path(__file__).resolve().parents[1] / "skills"
    STOPS: ClassVar[tuple[type[Exception], ...]] = (
        NoSliceLeftError,
        UnresolvableRepoOrBaseError,
        UnreadableIssueError,
        UnreadableRunError,
        ImpossibleTransitionError,
        ProtectedBranchError,
        BranchMismatchError,
        DiffNotReadableError,
        MeasuredCallError,
        ProcessTimedOutError,
        UnreadableForumError,
        LaggingSearchIndexError,
        NoPullRequestError,
        RunNotClosedError,
        GhCommandFailedError,
        GitCommandFailedError,
        ProcessNotRunnableError,
        SourcesBudgetExceededError,
    )

    ORDER_STOPS: ClassVar[tuple[type[Exception], ...]] = (
        OrderRefusedError,
        ImpossibleTransitionError,
        UnreadableIssueError,
        UnreadableRunError,
        GhCommandFailedError,
    )

    def __init__(self, *, process: Process, budgets: Budgets, activity: ActivityReader | None = None) -> None:
        self._process = process
        self._budgets = budgets
        self._activity = activity

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        try:
            arguments = cls.parser().parse_args(argv)
        except SystemExit as refusal:
            return ExitCode.USAGE_ERROR if refusal.code else ExitCode.OK

        try:
            return cls._dispatched(arguments)
        except Exception as error:
            return cls._reported(f"{type(error).__name__}: {error}", ExitCode.RUN_INTERRUPTED)

    @classmethod
    def _dispatched(cls, arguments: argparse.Namespace) -> int:
        budgets = Budgets()

        match Subcommand(arguments.command):
            case Subcommand.VERIFY:
                result = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets).verify(
                    repo=arguments.repo, base=arguments.base, slice_id=arguments.slice_id
                )
            case Subcommand.EXPLAIN:
                result = cls.explain(request=sys.stdin.read(), budgets=budgets)
            case Subcommand.RUN:
                result = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets).run(
                    ConductSliceParams(
                        repo=arguments.repo,
                        issue=arguments.issue,
                        root=str(Path(arguments.repo_root).resolve()),
                        worktree=None if arguments.worktree is None else str(Path(arguments.worktree).resolve()),
                        base=arguments.base,
                        logs=arguments.logs,
                        slice_id=arguments.slice_id,
                    )
                )
            case Subcommand.READ | Subcommand.SPEND | Subcommand.METRICS:
                result = cls._dispatched_over_the_ledgers(arguments)
            case Subcommand.DOCTOR | Subcommand.DISCOVER_CONVENTIONS | Subcommand.DISCOVER_CONTROLS | Subcommand.UPDATE:
                result = cls._dispatched_over_the_environment(arguments, budgets=budgets)
            case Subcommand.RESET | Subcommand.RETRY:
                result = cls._dispatched_over_a_subissue(arguments, budgets=budgets)
            case Subcommand.STATUS:
                result = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets).status(
                    repo=arguments.repo, issue=arguments.issue, as_json=arguments.json
                )
            case Subcommand.FOLLOW | Subcommand.TUI:
                result = cls._dispatched_for_the_interface(arguments, budgets=budgets)
            case Subcommand.REGISTER:
                result = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets).register(
                    repo=arguments.repo,
                    issue=arguments.issue,
                    reader=LocalEventReader(),
                    log=LocalEventLog(),
                    clock=SystemClock(),
                )

        return result

    @classmethod
    def _dispatched_over_the_environment(cls, arguments: argparse.Namespace, *, budgets: Budgets) -> int:
        match Subcommand(arguments.command):
            case Subcommand.DOCTOR:
                result = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets).doctor(
                    repo=arguments.repo, worktree=arguments.worktree, base=arguments.base
                )
            case Subcommand.DISCOVER_CONVENTIONS:
                result = cls.discover_conventions(repo_root=Path(arguments.repo))
            case Subcommand.DISCOVER_CONTROLS:
                result = cls.discover_controls(repo_root=Path(arguments.repo))
            case Subcommand.UPDATE:
                result = cls._updated(
                    check=arguments.check, budgets=budgets, running_program=Path(sys.argv[0]).absolute()
                )
            case _:
                raise ValueError(f"`{arguments.command}` is not a subcommand over the environment")

        return result

    @classmethod
    def _dispatched_for_the_interface(cls, arguments: argparse.Namespace, *, budgets: Budgets) -> int:
        match Subcommand(arguments.command):
            case Subcommand.FOLLOW:
                result = cls(
                    process=LocalProcess(budgets=budgets, subprocess=subprocess),
                    budgets=budgets,
                    activity=LocalActivityReader(),
                ).follow(
                    repo=arguments.repo,
                    once=arguments.once,
                    as_json=arguments.json,
                    reader=LocalEventReader(),
                    clock=SystemClock(),
                )
            case Subcommand.TUI:
                result = cls.tui(replacement=OsProcessReplacement(), issue=arguments.issue)
            case _:
                raise ValueError(f"`{arguments.command}` is not a subcommand of the interface")

        return result

    @classmethod
    def _dispatched_over_a_subissue(cls, arguments: argparse.Namespace, *, budgets: Budgets) -> int:
        cli = cls(process=LocalProcess(budgets=budgets, subprocess=subprocess), budgets=budgets)

        match Subcommand(arguments.command):
            case Subcommand.RESET:
                result = cli.reset(repo=arguments.repo, issue=arguments.issue)
            case Subcommand.RETRY:
                result = cli.retry(repo=arguments.repo, issue=arguments.issue, instruction=" ".join(arguments.text))
            case _:
                raise ValueError(f"`{arguments.command}` is not a subcommand over a subissue")

        return result

    @classmethod
    def _dispatched_over_the_ledgers(cls, arguments: argparse.Namespace) -> int:
        match Subcommand(arguments.command):
            case Subcommand.READ:
                result = cls.read(
                    repo=arguments.repo,
                    issue=arguments.issue,
                    worktree=arguments.worktree,
                    slice_id=arguments.slice_id,
                    step=Step(arguments.step),
                )
            case Subcommand.SPEND:
                result = cls.spend(
                    repo=arguments.repo, issue=arguments.issue, slice_id=arguments.slice_id, step=Step(arguments.step)
                )
            case Subcommand.METRICS:
                result = cls.metrics(
                    repo=arguments.repo,
                    since=cls._parsed_date(arguments.since, default=datetime(1970, 1, 1, tzinfo=UTC)),
                    until=cls._parsed_date(arguments.until, default=SystemClock().now()),
                    out=arguments.out,
                )

        return result

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog=cls.PROGRAM,
            description="Slice orchestrator.",
        )
        parser.add_argument("--version", action="version", version=InstalledVersion.read())
        subcommands = parser.add_subparsers(dest="command", required=True)

        verify = subcommands.add_parser(Subcommand.VERIFY, help="judge the index of a slice against its base")
        verify.add_argument("--repo", required=True, help="path of the slice's repo")
        verify.add_argument("--base", required=True, help="base branch the diff is taken against")
        verify.add_argument(
            "--slice", dest="slice_id", required=True, help="identifier of the slice the verdict belongs to"
        )

        subcommands.add_parser(
            Subcommand.EXPLAIN, help="say what comes after the run and the outcome read on standard input"
        )

        run = subcommands.add_parser(Subcommand.RUN, help="conduct the next slice of an issue until it has to stop")
        run.add_argument("issue", type=int, help="number of the issue whose next slice is conducted")
        run.add_argument("--repo", required=True, help="repo of the issue, as `<org>/<repo>`")
        run.add_argument(
            "--repo-root",
            default=".",
            help="root of the clone the worktree of the slice hangs from; the current directory by default",
        )
        run.add_argument(
            "--worktree",
            default=None,
            help=(
                "local path of a worktree mounted by hand where the slice is implemented and measured; it wins over "
                "the one the program derives under `--repo-root` and must belong to that clone"
            ),
        )
        run.add_argument("--base", required=True, help="branch the diff is taken against and the pull request targets")
        run.add_argument(
            "--logs",
            type=Path,
            default=ControlLogsDirectory.default(),
            help="directory where the log of each control is written",
        )
        run.add_argument(
            "--slice",
            dest="slice_id",
            default=None,
            help=(
                "identifier of the one slice to conduct, e.g. `slice-01`, or `PROJ-1234-01` when the feature "
                "declares a user story; without it, the next runnable one is chosen"
            ),
        )

        read = subcommands.add_parser(
            Subcommand.READ, help="print the conversation of the last call that served a slice's step, as text"
        )
        read.add_argument("--repo", required=True, help="repo of the issue the slice belongs to, as `<org>/<repo>`")
        read.add_argument("--issue", type=int, required=True, help="number of the subissue the slice belongs to")
        read.add_argument("--worktree", required=True, help="path of the slice's repo, as it was when the call ran")
        read.add_argument("--slice", dest="slice_id", required=True, help="identifier of the slice to read")
        read.add_argument("--step", required=True, choices=[str(x) for x in Step], help="step whose call is read")

        spend = subcommands.add_parser(
            Subcommand.SPEND, help="add up what the harness spent on the calls that served a slice's step"
        )
        spend.add_argument("--repo", required=True, help="repo of the issue the slice belongs to, as `<org>/<repo>`")
        spend.add_argument("--issue", type=int, required=True, help="number of the subissue the slice belongs to")
        spend.add_argument("--slice", dest="slice_id", required=True, help="identifier of the slice to add up")
        spend.add_argument("--step", required=True, choices=[str(x) for x in Step], help="step whose calls are summed")

        doctor = subcommands.add_parser(
            Subcommand.DOCTOR, help="check whether git, gh, claude and the skills the run needs are in place"
        )
        doctor.add_argument("--repo", default=None, help="repo to check read access to, as `<org>/<repo>`")
        doctor.add_argument(
            "--worktree", default=None, help="local path whose base branch is compared against its remote"
        )
        doctor.add_argument("--base", default=None, help="base branch compared against its remote")

        metrics = subcommands.add_parser(
            Subcommand.METRICS, help="emit the closed slices of a window already joined, and their view"
        )
        metrics.add_argument("--repo", default=None, help="limit to one repo, as `<org>/<repo>` (default: every repo)")
        metrics.add_argument("--since", default=None, help="earliest date included, as `YYYY-MM-DD` (default: all)")
        metrics.add_argument("--until", default=None, help="latest date included, as `YYYY-MM-DD` (default: now)")
        metrics.add_argument("--out", type=Path, required=True, help="path where the HTML view is written")

        reset = subcommands.add_parser(
            Subcommand.RESET,
            help="clear a subissue's persisted run and label it pending again, without touching git",
        )
        reset.add_argument("issue", type=int, help="number of the subissue to reset")
        reset.add_argument("--repo", required=True, help="repo of the issue the subissue belongs to")

        interface = subcommands.add_parser(
            Subcommand.TUI, help="open the interface that shows the slices, replacing this process"
        )
        interface.add_argument(
            "issue", type=int, nargs="?", default=None, help="number of the parent whose workspace is reopened"
        )

        discover_conventions = subcommands.add_parser(
            Subcommand.DISCOVER_CONVENTIONS,
            help="list the candidates to convention source of a repo, as `doc: <path>` or `skill: <path>` lines",
        )
        discover_conventions.add_argument("repo", nargs="?", default=".", help="root of the repo (default: .)")

        discover_controls = subcommands.add_parser(
            Subcommand.DISCOVER_CONTROLS,
            help="list the candidates to control of a repo, as `<name>: <command>  # <hint>` lines",
        )
        discover_controls.add_argument("repo", nargs="?", default=".", help="root of the repo (default: .)")

        update = subcommands.add_parser(
            Subcommand.UPDATE,
            help="install the latest release: the wheel, the interface binary and the skills",
        )
        update.add_argument(
            "--check", action="store_true", help="print the latest version if it is newer than this one, else nothing"
        )

        cls._add_the_orders(subcommands)

        cls._add_the_readers(subcommands)

        return parser

    @staticmethod
    def _add_the_orders(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        retry = subcommands.add_parser(
            Subcommand.RETRY,
            help="reopen a blocked or aborted slice with an instruction for the implementer, without launching the run",
        )
        retry.add_argument("issue", type=int, help="number of the subissue that is reopened")
        retry.add_argument("--repo", required=True, help="repo of the subissue, as `<org>/<repo>`")
        retry.add_argument("text", nargs="+", help="the instruction the implementer receives on the next run")

    @staticmethod
    def _add_the_readers(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        status = subcommands.add_parser(
            Subcommand.STATUS,
            help="print one line per slice of an issue with its state, step, spend and pull request, reading only",
        )
        status.add_argument("issue", type=int, help="number of the parent issue whose slices are shown")
        status.add_argument("--repo", required=True, help="repo of the issue, as `<org>/<repo>`")
        status.add_argument("--json", action="store_true", help="print each slice as a JSON object")

        follow = subcommands.add_parser(
            Subcommand.FOLLOW,
            help="print the last event of every slice and then one line per change, reading only the local events",
        )
        follow.add_argument("--repo", help="keep only the events of this repo, as `<org>/<repo>`")
        follow.add_argument("--once", action="store_true", help="print the snapshot and exit")
        follow.add_argument("--json", action="store_true", help="print each event as a JSON object")

        register = subcommands.add_parser(
            Subcommand.REGISTER,
            help="write a pending event for each open subissue of an issue that has none yet, for the interface",
        )
        register.add_argument("issue", type=int, help="number of the parent issue whose subissues are registered")
        register.add_argument("--repo", required=True, help="repo of the issue, as `<org>/<repo>`")

    @classmethod
    def tui(cls, *, replacement: ProcessReplacement, issue: int | None) -> int:
        argv = [cls.TUI_EXECUTABLE] if issue is None else [cls.TUI_EXECUTABLE, str(issue)]
        try:
            replacement.replaced_by(argv)
        except ExecutableNotFoundError:
            return cls._reported(
                f"`{cls.TUI_EXECUTABLE}` is not on the PATH: run `slice-runner update` to install it",
                ExitCode.TUI_NOT_INSTALLED,
            )

    @classmethod
    def _installation(cls, process: Process) -> UvProgramInstallation:
        return UvProgramInstallation(
            process=process, skill_library=LocalSkillLibrary(), packaged_skills=cls.PACKAGED_SKILLS
        )

    @classmethod
    def _newer_release(cls, process: Process, installation: UvProgramInstallation) -> ReadNewerRelease:
        return ReadNewerRelease(
            releases=GhProgramReleases(process=process, repo=cls.RELEASES_REPO),
            installation=installation,
            host=LocalHostPlatform(system=platform.system(), machine=platform.machine()),
        )

    @classmethod
    def _updated(cls, *, check: bool, budgets: Budgets, running_program: Path) -> int:
        if check:
            process = LocalProcess(
                budgets=replace(budgets, process_timeout_seconds=cls.CHECK_TIMEOUT_SECONDS), subprocess=subprocess
            )
            return cls.update_check(
                query=cls._newer_release(process, cls._installation(process)), running_program=running_program
            )

        process = LocalProcess(budgets=budgets, subprocess=subprocess)
        return cls.update(
            action=UpdateProgram(
                live_runs=PgrepLiveRuns(process=process),
                host=LocalHostPlatform(system=platform.system(), machine=platform.machine()),
                releases=GhProgramReleases(process=process, repo=cls.RELEASES_REPO),
                installation=cls._installation(process),
            ),
            replacement=OsProcessReplacement(),
        )

    @classmethod
    def update(cls, *, action: UpdateProgram, replacement: ProcessReplacement) -> int:
        try:
            result = action.execute()
        except LiveRunsError as error:
            return cls._reported(f"the update does not run over live runs: {error}", ExitCode.LIVE_RUNS)
        except UnsupportedPlatformError as error:
            return cls._reported(f"the update has no binary for this machine: {error}", ExitCode.UNSUPPORTED_PLATFORM)

        match result:
            case WheelInstalled(program=program):
                replacement.replaced_by([str(program), Subcommand.UPDATE])
            case UpdateCompleted():
                return ExitCode.OK
            case ReleaseIncomplete(version=version):
                return cls._reported(f"version {version} does not have all its files yet", ExitCode.RELEASE_INCOMPLETE)

    @classmethod
    def update_check(cls, *, query: ReadNewerRelease, running_program: Path) -> int:
        for version in query.execute(ReadNewerReleaseParams(running_program=running_program)).versions:
            print(version)

        return ExitCode.OK

    @classmethod
    def discover_conventions(cls, *, repo_root: Path) -> int:
        for source in ConventionSourceDiscovery.of(repo_root):
            print(f"{source.kind}: {source.path}")

        return ExitCode.OK

    @classmethod
    def discover_controls(cls, *, repo_root: Path) -> int:
        for candidate in ControlCandidateDiscovery.of(repo_root):
            hint = f"{candidate.hint} ({candidate.source})" if candidate.hint else f"({candidate.source})"
            print(f"{candidate.name}: {candidate.command}  # {hint}")

        return ExitCode.OK

    @classmethod
    def explain(cls, *, request: str, budgets: Budgets) -> int:
        try:
            asked = TransitionRequestPayload.read(request)
            transition = StateMachine(budgets=budgets).after(asked.run.to_domain(), asked.outcome)
        except (ImpossibleTransitionError, UnreadableRunError) as error:
            return cls._reported(f"there is no transition to explain: {error}", ExitCode.USAGE_ERROR)

        print(json.dumps(TransitionPayload.from_domain(transition).to_contract(), ensure_ascii=False))

        return ExitCode.OK

    @classmethod
    def read(cls, *, repo: str, issue: int, worktree: str, slice_id: str, step: Step) -> int:
        clock = SystemClock()
        try:
            result = ReadConversation(trace=LocalCallTrace(clock=clock), log=LocalConversationLog()).execute(
                ReadConversationParams(repo=repo, issue=issue, worktree=worktree, slice_id=slice_id, step=step)
            )
        except (NoConversationRecordedError, ConversationNotFoundError) as error:
            return cls._reported(f"there is no conversation to read: {error}", ExitCode.USAGE_ERROR)
        except (UnreadableCallTraceError, UnreadableConversationError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        print(
            ConversationReport(
                slice_id=slice_id, step=step, session=result.session, conversation=result.conversation
            ).rendered()
        )

        return ExitCode.OK

    @classmethod
    def spend(cls, *, repo: str, issue: int, slice_id: str, step: Step) -> int:
        clock = SystemClock()
        try:
            spend = SpendOfStep(trace=LocalCallTrace(clock=clock), spend_log=LocalCallSpendLog(clock=clock)).execute(
                SpendOfStepParams(repo=repo, issue=issue, slice_id=slice_id, step=step)
            )
        except (UnreadableCallTraceError, UnreadableCallSpendLogError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        print(json.dumps(SpendPayload.from_domain(spend).to_contract(), ensure_ascii=False))

        return ExitCode.OK

    @classmethod
    def metrics(cls, *, repo: str | None, since: datetime, until: datetime, out: Path) -> int:
        clock = SystemClock()
        scope = ClosedSliceScope.of_a_repo_between(repo=repo, since=since, until=until)
        try:
            records = ListClosedSlices(metrics_log=LocalMetricsLog(clock=clock)).execute(
                ListClosedSlicesParams(scope=scope)
            )
            role_spend = SpendByRole(
                trace=LocalCallTrace(clock=clock), spend_log=LocalCallSpendLog(clock=clock)
            ).execute(SpendByRoleParams(records=records))
        except (UnreadableCallTraceError, UnreadableCallSpendLogError, UnreadableMetricsLogError) as error:
            return cls._reported(f"the durable record cannot be read: {error}", ExitCode.USAGE_ERROR)

        for record in records:
            print(json.dumps(ClosedSliceRecordPayload.from_domain(record).to_contract(), ensure_ascii=False))

        metrics = ClosedSliceMetrics.of(records)
        print(json.dumps(ClosedSliceMetricsPayload.from_domain(metrics).to_contract(), ensure_ascii=False))

        view = ClosedSliceMetricsView.rendered(scope=scope, records=records, role_spend=role_spend, metrics=metrics)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(view, encoding="utf-8")

        return ExitCode.OK

    @staticmethod
    def _parsed_date(value: str | None, *, default: datetime) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC) if value else default

    def verify(self, *, repo: str, base: str, slice_id: str) -> int:
        try:
            verification = self._action().execute(self._params(worktree=repo, base=base, slice_id=slice_id))
        except (
            UnresolvableRepoOrBaseError,
            DiffNotReadableError,
            InvalidHarnessOutputError,
            ProcessTimedOutError,
            ProcessNotRunnableError,
            SourcesBudgetExceededError,
            MalformedSliceIdError,
        ) as error:
            return self._why_verify_failed(error)

        self._warn_about(verification.denied_reads)
        print(json.dumps(VerdictPayload.from_domain(verification.verdict).to_contract(), ensure_ascii=False))

        return ExitCode.of(verification.verdict.ruling)

    def _why_verify_failed(
        self,
        error: UnresolvableRepoOrBaseError
        | DiffNotReadableError
        | InvalidHarnessOutputError
        | ProcessTimedOutError
        | ProcessNotRunnableError
        | SourcesBudgetExceededError
        | MalformedSliceIdError,
    ) -> int:
        match error:
            case MalformedSliceIdError():
                return self._reported(f"the slice identifier requested is not canonical: {error}", ExitCode.USAGE_ERROR)
            case UnresolvableRepoOrBaseError():
                return self._reported(f"the repo or the base requested do not resolve: {error}", ExitCode.USAGE_ERROR)
            case DiffNotReadableError():
                return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
            case InvalidHarnessOutputError():
                return self._reported(f"the judge left no usable verdict: {error}", ExitCode.NO_USABLE_VERDICT)
            case ProcessTimedOutError() | ProcessNotRunnableError() | SourcesBudgetExceededError():
                return self._why_the_verify_call_failed(error)

    def _why_the_verify_call_failed(
        self, error: ProcessTimedOutError | ProcessNotRunnableError | SourcesBudgetExceededError
    ) -> int:
        match error:
            case ProcessTimedOutError():
                return self._reported(
                    f"a process the run needs never came back and was killed at its cap: {error}",
                    ExitCode.PROCESS_TIMED_OUT,
                )
            case ProcessNotRunnableError():
                return self._reported(
                    f"a process the run needs could not be launched, so there is no verdict: {error}",
                    ExitCode.NO_USABLE_VERDICT,
                )
            case SourcesBudgetExceededError():
                return self._reported(
                    f"the declared sources are over the budget, so no prompt was sent: {error}",
                    ExitCode.SOURCES_BUDGET_EXCEEDED,
                )

    def run(self, params: ConductSliceParams) -> int:
        params.logs.mkdir(parents=True, exist_ok=True)

        try:
            conducted = self._conductor().execute(params)
        except self.STOPS as error:
            return self._why_the_run_stopped(error)

        self._warn_about_the_draft_pull_request(conducted)
        self._warn_about_the_blocked_worktree(conducted)
        self._warn_about_the_kept_worktree(conducted)
        print(json.dumps(ConductedSlicePayload.from_domain(conducted).to_contract(), ensure_ascii=False))

        return ExitCode.of_the_halt(halt=conducted.halt, closure=conducted.closure)

    @staticmethod
    def _warn_about_the_draft_pull_request(conducted: ConductSliceResult) -> None:
        if conducted.halt is not Halt.WAIT_EXHAUSTED or conducted.step is not Step.AWAIT_MERGE:
            return

        print(
            f"pull request #{conducted.pull_request} was opened as a draft; take it out of draft for the merge "
            "to happen, reinvoking alone will not move it",
            file=sys.stderr,
        )

    @staticmethod
    def _warn_about_the_blocked_worktree(conducted: ConductSliceResult) -> None:
        if conducted.closure.reason is not ClosingReason.WORKTREE:
            return
        if conducted.worktree_retirement is WorktreeRetirement.KEPT_UNEXPECTED:
            command = KeptWorktreeComment.removal_command(conducted.conflicting_path)
            print(
                f"a worktree nobody expected is left at {conducted.conflicting_path}, so it is neither reused "
                f"nor mounted over; resolve it by hand with `{command}` and reinvoke with a retry instruction",
                file=sys.stderr,
            )
            return

        print(
            f"the worktree of the slice cannot be mounted because of {conducted.conflicting_path}; "
            "free that path or branch and reinvoke with a retry instruction",
            file=sys.stderr,
        )

    @staticmethod
    def _warn_about_the_kept_worktree(conducted: ConductSliceResult) -> None:
        retirement = conducted.worktree_retirement
        if retirement is WorktreeRetirement.KEPT_UNEXPECTED or not retirement.kept:
            return

        print(
            f"the worktree of the slice stayed at {conducted.worktree} ({conducted.worktree_retirement})",
            file=sys.stderr,
        )

    def doctor(self, *, repo: str | None = None, worktree: str | None = None, base: str | None = None) -> int:
        readiness = CheckReadiness(
            ports=CheckReadinessPorts(
                toolbox=LocalToolbox(process=self._process),
                forum=GhForum(call=self._gh_call(clock=SystemClock())),
                branches=GitBranches(process=self._process),
                skills=LocalSkillLibrary(),
                plugins=LocalPluginRegistry(),
                program_version=InstalledVersion(),
            )
        ).execute(CheckReadinessParams(repo=repo, worktree=worktree, base=base))

        print(ReadinessReport(readiness=readiness).rendered())

        return ExitCode.OK if readiness.ready else ExitCode.ENVIRONMENT_NOT_READY

    def reset(self, *, repo: str, issue: int) -> int:
        clock = SystemClock()
        repository = GhRunRepository(call=self._gh_call(clock=clock))
        try:
            subissue = repository.read_subissue(repo=repo, issue=issue)
            reset = ResetSlice(repository=repository, clock=clock).execute(
                ResetSliceParams(repo=repo, subissue=subissue)
            )
        except (UnreadableIssueError, UnreadableRunError, NoRecognizableSpecError) as error:
            return self._reported(f"there is no spec to reset: {error}", ExitCode.USAGE_ERROR)
        except GhCommandFailedError as error:
            return self._reported(f"the reset could not be written: {error}", ExitCode.RUN_INTERRUPTED)

        print(
            f"subissue #{issue} was reset to `{reset.subissue.label}`; the branch `{reset.subissue.branch}` and "
            "the working tree were left untouched"
        )

        return ExitCode.OK

    def retry(self, *, repo: str, issue: int, instruction: str) -> int:
        if not instruction.strip():
            return self._reported("a retry needs the instruction as text", ExitCode.USAGE_ERROR)

        repository = GhRunRepository(call=self._gh_call(clock=SystemClock()))
        try:
            subissue = repository.read_subissue(repo=repo, issue=issue)
            ReopenSlice(repository=repository, machine=StateMachine(budgets=self._budgets)).execute(
                ReopenSliceParams(repo=repo, subissue=subissue, instruction=instruction)
            )
        except self.ORDER_STOPS as error:
            return self._why_the_order_stopped(error)

        print(f"subissue #{issue} is reopened: the next `run` hands the instruction to the implementer")

        return ExitCode.OK

    def _why_the_order_stopped(self, error: Exception) -> ExitCode:
        match error:
            case OrderRefusedError() | ImpossibleTransitionError():
                return self._reported(f"the order was refused: {error}", ExitCode.ORDER_REFUSED)
            case UnreadableIssueError() | UnreadableRunError():
                return self._reported(f"the order cannot be given as asked: {error}", ExitCode.USAGE_ERROR)
            case _:
                return self._reported(f"the order could not be written: {error}", ExitCode.RUN_INTERRUPTED)

    def status(self, *, repo: str, issue: int, as_json: bool = False) -> int:
        clock = SystemClock()
        gh_call = self._gh_call(clock=clock)
        try:
            statuses = ShowFeatureStatus(
                repository=GhRunRepository(call=gh_call),
                forum=GhForum(call=gh_call),
                metrics=LocalMetricsLog(clock=clock),
                spend_log=LocalCallSpendLog(clock=clock),
            ).execute(ShowFeatureStatusParams(repo=repo, issue=issue))
        except (
            LaggingSearchIndexError,
            UnreadableIssueError,
            UnreadableForumError,
            UnreadableMetricsLogError,
        ) as error:
            return self._reported(f"the status of the feature could not be read: {error}", ExitCode.USAGE_ERROR)
        except GhCommandFailedError as error:
            return self._reported(f"the status of the feature could not be read: {error}", ExitCode.RUN_INTERRUPTED)

        if as_json:
            for line in FeatureStatusJsonReport(statuses=statuses).lines():
                print(line)
        else:
            print(FeatureStatusReport(statuses=statuses).rendered())

        return ExitCode.OK

    def follow(
        self,
        *,
        repo: str | None,
        once: bool,
        reader: EventReader,
        clock: Clock,
        as_json: bool = False,
    ) -> int:
        query = FollowEvents(reader=reader)
        live = FollowActivity(reader=self._activity) if as_json and self._activity is not None else None
        cursors = ActivityCursors()
        try:
            followed = query.execute(FollowEventsParams(cursor=EventCursor.start(), repo=repo))
            self._printed(self._history_of(followed) if as_json else followed.snapshot, as_json=as_json)
            cursors = self._printed_activity(live, followed.snapshot, cursors)
            while not once:
                clock.sleep(seconds=self._budgets.seconds_between_follow_reads)
                followed = query.execute(
                    FollowEventsParams(cursor=followed.cursor, snapshot=followed.snapshot, repo=repo)
                )
                self._printed(followed.changes, as_json=as_json)
                cursors = self._printed_activity(live, followed.snapshot, cursors)
        except KeyboardInterrupt:
            return ExitCode.OK
        except (UnreadableEventLogError, UnreadableActivityLogError) as error:
            return self._reported(f"the events could not be followed: {error}", ExitCode.USAGE_ERROR)

        return ExitCode.OK

    def register(self, *, repo: str, issue: int, reader: EventReader, log: EventLog, clock: Clock) -> int:
        try:
            RegisterPendingSlices(
                children=GhChildIssues(call=self._gh_call(clock=clock)),
                reader=reader,
                log=log,
                clock=clock,
                budgets=self._budgets,
            ).execute(RegisterPendingSlicesParams(repo=repo, parent=issue))
        except (UnreadableEventLogError, UnreadableIssueError) as error:
            return self._reported(f"the pending slices could not be registered: {error}", ExitCode.USAGE_ERROR)
        except GhCommandFailedError as error:
            return self._reported(f"the pending slices could not be registered: {error}", ExitCode.RUN_INTERRUPTED)

        return ExitCode.OK

    @staticmethod
    def _printed_activity(
        live: FollowActivity | None, snapshot: tuple[Event, ...], cursors: ActivityCursors
    ) -> ActivityCursors:
        if live is None:
            return cursors

        followed = live.execute(FollowActivityParams(snapshot=snapshot, cursors=cursors))
        for line in ActivityFollowJsonReport(activities=followed.activities).lines():
            print(line, flush=True)

        return followed.cursors

    @staticmethod
    def _history_of(followed: FollowEventsResult) -> tuple[Event, ...]:
        last_change = {event.slice_key: event for event in followed.changes}
        latest_not_yet_told = tuple(
            event for event in followed.snapshot if last_change.get(event.slice_key) is not event
        )

        return followed.changes + latest_not_yet_told

    @staticmethod
    def _printed(events: tuple[Event, ...], *, as_json: bool) -> None:
        report = EventFollowJsonReport(events=events) if as_json else EventFollowReport(events=events)
        for line in report.lines():
            print(line, flush=True)

    def _why_the_run_stopped(self, error: Exception) -> ExitCode:
        match error:
            case NoSliceLeftError():
                return self._reported(f"there is no slice left to run: {error}", ExitCode.NO_SLICE_LEFT)
            case (
                UnresolvableRepoOrBaseError()
                | UnreadableIssueError()
                | UnreadableRunError()
                | ImpossibleTransitionError()
                | ProtectedBranchError()
                | BranchMismatchError()
            ):
                return self._reported(f"the run cannot be conducted as asked: {error}", ExitCode.USAGE_ERROR)
            case DiffNotReadableError():
                return self._reported(f"there is no diff to verify: {error}", ExitCode.NO_DIFF)
            case MeasuredCallError():
                return self._reported(f"the harness left nothing usable behind: {error}", ExitCode.NO_USABLE_VERDICT)
            case ProcessTimedOutError() | SourcesBudgetExceededError():
                return self._why_the_call_failed(error)
            case _:
                return self._reported(f"the run stopped before reaching a halt: {error}", ExitCode.RUN_INTERRUPTED)

    def _why_the_call_failed(self, error: ProcessTimedOutError | SourcesBudgetExceededError) -> ExitCode:
        match error:
            case ProcessTimedOutError():
                return self._reported(
                    f"a call the run made never came back and was killed at its cap: {error}",
                    ExitCode.PROCESS_TIMED_OUT,
                )
            case SourcesBudgetExceededError():
                return self._reported(
                    f"the declared sources are over the budget, so no prompt was sent: {error}",
                    ExitCode.SOURCES_BUDGET_EXCEEDED,
                )

    def _conductor(self) -> ConductSlice:
        clock = SystemClock()
        gh_call = self._gh_call(clock=clock)
        repository = GhRunRepository(call=gh_call)
        branches = GitBranches(process=self._process)
        worktrees = GitWorktrees(process=self._process)
        forum = GhForum(call=gh_call)
        workspace = GitWorkspace(process=self._process)
        machine = StateMachine(budgets=self._budgets)
        reader = ProcessSourceReader(process=self._process, budgets=self._budgets)
        captures = ProcessDesignCaptureStore(process=self._process)
        corpus = LocalCorpus(clock=clock)
        debt_ledger = LocalDebtLedger(clock=clock)
        activity = LocalActivityLog(clock=clock)
        calls = HarnessInvocationRunner(
            process=self._process,
            telemetry=HarnessTelemetry(
                trace=LocalCallTrace(clock=clock),
                turns=StderrTurnLog(),
                activity=activity,
                spend_log=LocalCallSpendLog(clock=clock),
                tool_uses=self._tool_uses(clock=clock),
            ),
        )

        return ConductSlice(
            use_cases=ConductSliceUseCases(
                select=SelectSlice(repository=repository),
                prechecks=RunPrechecks(branches=branches, forum=forum),
                mount=MountWorktree(worktrees=worktrees),
                retire=RetireWorktree(worktrees=worktrees),
                check_sources=CheckSources(sources=reader),
                read_captures=ReadDesignCaptures(captures=captures),
                implement=ImplementSlice(
                    implementer=ClaudeImplementer(calls=calls, reader=reader),
                    reader=GitDiffReader(process=self._process),
                    debt_ledger=debt_ledger,
                    captures=captures,
                    workspace=workspace,
                ),
                stage=StageSlice(workspace=workspace),
                commit=CommitRound(
                    workspace=workspace, events=LocalEventLog(), clock=clock, budgets=self._budgets, pid=os.getpid()
                ),
                rescue=RescueStagedWork(workspace=workspace),
                run_controls=RunControls(controls=LocalControlRunner(process=self._process), activity=activity),
                verify=self._action(clock=clock, corpus=corpus),
                mount_comparison=MountComparison(pages=ProcessComparisonPages(process=self._process)),
                deliver=DeliverSlice(workspace=workspace, forum=forum),
                close=CloseParent(repository=repository),
                record_step=RecordStep(
                    repository=repository, events=LocalEventLog(), clock=clock, budgets=self._budgets, pid=os.getpid()
                ),
                record_closure=RecordClosure(
                    metrics=LocalMetricsLog(clock=clock),
                    repository=repository,
                    spend_log=LocalCallSpendLog(clock=clock),
                    corpus=corpus,
                    debt_ledger=debt_ledger,
                ),
                record_start=RecordStart(events=LocalEventLog(), clock=clock, budgets=self._budgets, pid=os.getpid()),
                read_ci=ReadCiStatus(ci=GhCi(call=gh_call), forum=forum),
                read_pull_request=ReadPullRequestStatus(forum=forum),
                catch_up=CatchUpBranch(branches=BranchesWithoutCatchUp(branches=branches)),
            ),
            ports=ConductSlicePorts(
                repository=repository,
                forum=forum,
                clock=clock,
                pull_request=SlicePullRequest(),
            ),
            machine=machine,
            budgets=self._budgets,
            models=RoleModels(
                implement=ImplementerInvocation.MODEL,
                verify=JudgeInvocation.MODEL,
                implement_effort=ImplementerInvocation.EFFORT,
                verify_effort=JudgeInvocation.EFFORT,
            ),
        )

    def _gh_call(self, *, clock: Clock) -> GhCall:
        return GhCall(process=self._process, policy=GhRetryPolicy(budgets=self._budgets), clock=clock)

    def _action(self, *, clock: Clock | None = None, corpus: Corpus | None = None) -> VerifySlice:
        used = clock or SystemClock()

        return VerifySlice(
            reader=GitDiffReader(process=self._process),
            verifier=ClaudeVerifier(
                calls=HarnessInvocationRunner(
                    process=self._process,
                    telemetry=HarnessTelemetry(
                        trace=LocalCallTrace(clock=used),
                        turns=StderrTurnLog(),
                        activity=LocalActivityLog(clock=used),
                        spend_log=LocalCallSpendLog(clock=used),
                        tool_uses=self._tool_uses(clock=used),
                    ),
                ),
                reader=ProcessSourceReader(process=self._process, budgets=self._budgets),
            ),
            judge=SliceVerifierJudge.adversarial(),
            skills=LocalSkillLibrary(),
            corpus=corpus or LocalCorpus(clock=used),
        )

    @staticmethod
    def _tool_uses(*, clock: Clock) -> ConversationToolUseRecorder:
        return ConversationToolUseRecorder(
            conversations=LocalConversationLog(), tool_use_log=LocalToolUseLog(clock=clock)
        )

    @staticmethod
    def _warn_about(denied_reads: tuple[str, ...]) -> None:
        if not denied_reads:
            return

        print(
            f"the judge was denied {len(denied_reads)} read(s), so it may have measured with an incomplete "
            f"yardstick: {', '.join(denied_reads)}",
            file=sys.stderr,
        )

    @staticmethod
    def _params(*, worktree: str, base: str, slice_id: str) -> VerifySliceParams:
        return VerifySliceParams(
            repo="",
            issue=0,
            worktree=worktree,
            base=base,
            slice_id=slice_id,
            verify_round=1,
            prior_art="",
            signal="",
            excludes="",
            replaces="",
            criteria=(),
            sources=(),
            checklist=(),
            prior_findings=(),
            debt=(),
            decisions=(),
            deviations=(),
            designs=(),
            captures=DesignCaptures(captures=()),
            compares_with_the_last_verification=False,
        )

    @staticmethod
    def _reported(reason: str, code: ExitCode) -> ExitCode:
        print(reason, file=sys.stderr)

        return code
