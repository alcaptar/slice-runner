from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, ClassVar, Literal

from slice_runner.application.actions.catch_up_branch import CatchUpBranchParams
from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.application.actions.commit_round import CommitRoundParams
from slice_runner.application.actions.deliver_slice import DeliverSliceParams
from slice_runner.application.actions.implement_slice import ImplementSliceParams
from slice_runner.application.actions.mount_comparison import MountComparisonParams
from slice_runner.application.actions.mount_worktree import MountWorktreeParams, MountWorktreeResult
from slice_runner.application.actions.record_closure import RecordClosureParams
from slice_runner.application.actions.record_start import RecordStartParams
from slice_runner.application.actions.record_step import RecordStepParams
from slice_runner.application.actions.rescue_staged_work import RescueStagedWorkParams
from slice_runner.application.actions.retire_worktree import RetireWorktreeParams
from slice_runner.application.actions.run_controls import RunControlsParams
from slice_runner.application.actions.stage_slice import StageSliceParams
from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.application.queries.check_sources import CheckSourcesParams
from slice_runner.application.queries.read_ci_status import ReadCiStatusParams
from slice_runner.application.queries.read_design_captures import ReadDesignCapturesParams
from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatusParams
from slice_runner.application.queries.run_prechecks import RunPrechecksParams
from slice_runner.application.queries.select_slice import SelectSliceParams
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closing_worktree import ClosingWorktree
from slice_runner.domain.closure import Closure
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.exceptions import (
    DirtyIndexError,
    ImpossibleTransitionError,
    MeasuredCallError,
    NoPullRequestError,
    NoSliceLeftError,
    UnchangedDiffError,
)
from slice_runner.domain.feature_slice import FeatureSlice
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.prechecks import Prechecks
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run import Run
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.domain.transition import Transition
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.domain.worktree_retirement_policy import WorktreeRetirementPolicy

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from slice_runner.application.actions.catch_up_branch import CatchUpBranch
    from slice_runner.application.actions.close_parent import CloseParent
    from slice_runner.application.actions.commit_round import CommitRound
    from slice_runner.application.actions.deliver_slice import DeliverSlice
    from slice_runner.application.actions.implement_slice import ImplementSlice
    from slice_runner.application.actions.mount_comparison import MountComparison
    from slice_runner.application.actions.mount_worktree import MountWorktree
    from slice_runner.application.actions.record_closure import RecordClosure
    from slice_runner.application.actions.record_start import RecordStart
    from slice_runner.application.actions.record_step import RecordStep
    from slice_runner.application.actions.rescue_staged_work import RescueStagedWork
    from slice_runner.application.actions.retire_worktree import RetireWorktree
    from slice_runner.application.actions.run_controls import RunControls
    from slice_runner.application.actions.stage_slice import StageSlice
    from slice_runner.application.actions.verify_slice import VerifySlice
    from slice_runner.application.queries.check_sources import CheckSources
    from slice_runner.application.queries.read_ci_status import ReadCiStatus
    from slice_runner.application.queries.read_design_captures import ReadDesignCaptures
    from slice_runner.application.queries.read_pull_request_status import ReadPullRequestStatus
    from slice_runner.application.queries.run_prechecks import RunPrechecks
    from slice_runner.application.queries.select_slice import SelectSlice, SelectSliceResult
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.pull_request_writer import PullRequestWriter
    from slice_runner.domain.reported_path import ReportedPath
    from slice_runner.domain.role_models import RoleModels
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.state_machine import StateMachine
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.verdict import Verdict


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceParams:
    repo: str
    issue: int
    root: str
    worktree: str | None
    base: str
    logs: Path
    slice_id: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceResult:
    halt: Halt
    closure: Closure
    step: Step
    precheck: PrecheckResult | None = None
    pull_request: int | None = None
    conflicting_path: str = ""
    worktree: str = ""
    worktree_retirement: WorktreeRetirement = WorktreeRetirement.NOT_MOUNTED


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceProgress:
    params: ConductSliceParams
    worktree: str
    chosen: SelectSliceResult
    run: Run
    label: IssueLabel | None
    paths: tuple[ReportedPath, ...] = field(default=())
    debt: tuple[str, ...] = field(default=())
    deviations: tuple[str, ...] = field(default=())
    verdicts: tuple[Verdict, ...] = field(default=())
    spends: tuple[HarnessSpend, ...] = field(default=())
    control_logs: tuple[Path, ...] = field(default=())
    hygiene_refusal: str = ""
    pull_request: int | None = None
    comparison: str | None = None
    waited_seconds: int = 0
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    conflicting_paths: tuple[str, ...] = field(default=())
    expects_a_tree: bool = True
    tree_left_behind: bool = False

    @property
    def spend(self) -> HarnessSpend:
        return HarnessSpend.summing(self.spends)

    @property
    def findings_of_the_last_round(self) -> tuple[Finding, ...]:
        return self.verdicts[-1].findings if self.verdicts else ()

    @property
    def judged_in_this_invocation(self) -> bool:
        return bool(self.verdicts)

    @property
    def subissue(self) -> SubIssue:
        return self.chosen.subissue

    @property
    def parent(self) -> ParentIssue:
        return self.chosen.parent


@dataclass(frozen=True, kw_only=True, slots=True)
class SteppedSlice:
    progress: ConductSliceProgress
    outcome: Outcome
    call_died: bool = False
    verdict_recorded: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class HaltedSlice:
    progress: ConductSliceProgress
    halt: Halt


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSliceUseCases:
    select: SelectSlice
    prechecks: RunPrechecks
    mount: MountWorktree
    retire: RetireWorktree
    check_sources: CheckSources
    read_captures: ReadDesignCaptures
    implement: ImplementSlice
    stage: StageSlice
    commit: CommitRound
    rescue: RescueStagedWork
    run_controls: RunControls
    verify: VerifySlice
    mount_comparison: MountComparison
    deliver: DeliverSlice
    close: CloseParent
    record_step: RecordStep
    record_closure: RecordClosure
    record_start: RecordStart
    read_ci: ReadCiStatus
    read_pull_request: ReadPullRequestStatus
    catch_up: CatchUpBranch


@dataclass(frozen=True, kw_only=True, slots=True)
class ConductSlicePorts:
    repository: RunRepository
    forum: Forum
    clock: Clock
    pull_request: PullRequestWriter


class ConductSlice:
    def __init__(
        self,
        *,
        use_cases: ConductSliceUseCases,
        ports: ConductSlicePorts,
        machine: StateMachine,
        budgets: Budgets,
        models: RoleModels,
    ) -> None:
        self._select = use_cases.select
        self._prechecks = use_cases.prechecks
        self._mount = use_cases.mount
        self._retire = use_cases.retire
        self._check_sources = use_cases.check_sources
        self._read_captures = use_cases.read_captures
        self._implement = use_cases.implement
        self._stage = use_cases.stage
        self._commit = use_cases.commit
        self._rescue = use_cases.rescue
        self._run_controls = use_cases.run_controls
        self._verify = use_cases.verify
        self._mount_comparison = use_cases.mount_comparison
        self._deliver = use_cases.deliver
        self._close = use_cases.close
        self._record_step = use_cases.record_step
        self._record_closure = use_cases.record_closure
        self._record_start = use_cases.record_start
        self._read_ci = use_cases.read_ci
        self._read_pull_request = use_cases.read_pull_request
        self._catch_up = use_cases.catch_up
        self._repository = ports.repository
        self._forum = ports.forum
        self._clock = ports.clock
        self._pull_request = ports.pull_request
        self._machine = machine
        self._budgets = budgets
        self._models = models

    def execute(self, params: ConductSliceParams) -> ConductSliceResult:
        try:
            chosen = self._select.execute(
                SelectSliceParams(repo=params.repo, issue=params.issue, slice_id=params.slice_id)
            )
        except NoSliceLeftError as unselectable:
            reconciled = sum(
                self._closing_a_merge_missed_between_invocations(params, dangling) for dangling in unselectable.dangling
            )
            raise self._reported_after_reconciling(unselectable, reconciled) from unselectable

        for dangling in chosen.dangling:
            self._closing_a_merge_missed_between_invocations(params, dangling)
        expects_a_tree = self._expects_a_tree(params, chosen)
        run = chosen.subissue.run or Run(step=Step.MOUNT_WORKTREE)
        worktree = params.worktree or chosen.subissue.slice_id.worktree_under(params.root)
        progress = ConductSliceProgress(
            params=params,
            worktree=worktree,
            chosen=chosen,
            run=run,
            label=chosen.subissue.label,
            spends=(run.spend,) if run.spend.measured else (),
            comparison=self._comparison_of_a_resumed_run(chosen, worktree=worktree),
            expects_a_tree=expects_a_tree,
        )
        of_the_subissue = Prechecks.of_the_subissue(chosen.subissue)
        if of_the_subissue is not PrecheckOutcome.CLEAR:
            return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=PrecheckResult(outcome=of_the_subissue))
        if chosen.subissue.run is not None:
            return self._resuming(progress)
        return self._prechecking(progress)

    @staticmethod
    def _comparison_of_a_resumed_run(chosen: SelectSliceResult, *, worktree: str) -> str | None:
        run = chosen.subissue.run
        if run is None or not run.step.has_opened_the_pull_request():
            return None

        return DesignCapturesDirectory.comparison_page_of(worktree, chosen.subissue.designs_under(chosen.parent))

    @staticmethod
    def _expects_a_tree(params: ConductSliceParams, chosen: SelectSliceResult) -> bool:
        return params.worktree is not None or WorktreeRetirementPolicy.expects_a_tree(
            label=chosen.subissue.label, run=chosen.subissue.run
        )

    def _resuming(self, progress: ConductSliceProgress) -> ConductSliceResult:
        return self._mounting(progress, then=self._resuming_on_the_mounted_worktree)

    def _resuming_on_the_mounted_worktree(self, progress: ConductSliceProgress) -> ConductSliceResult:
        if progress.run.step is Step.MOUNT_WORKTREE:
            return self._reading_the_sources(progress)
        if self._staged_work_waits_at(progress.run.step):
            self._rescuing_staged_work(progress)
        if progress.run.step.is_after_delivery():
            return self._conducting(progress)

        return self._caught_up_before_conducting(progress)

    def _mounting(
        self, progress: ConductSliceProgress, *, then: Callable[[ConductSliceProgress], ConductSliceResult]
    ) -> ConductSliceResult:
        mounted = self._mount.execute(
            MountWorktreeParams(
                root=progress.params.root,
                worktree=progress.worktree,
                branch=progress.subissue.branch,
                base=progress.params.base,
                expects_a_tree=progress.expects_a_tree,
            )
        )
        if mounted.outcome is Outcome.WORKTREE_TAKEN or mounted.outcome is Outcome.WORKTREE_LEFT_BEHIND:
            return self._blocked_by_the_worktree(
                self._with_the_tree_left_behind(progress, mounted),
                mounted.outcome,
            )

        return then(self._with_the_tree_expected_from_now_on(progress))

    @staticmethod
    def _with_the_tree_left_behind(
        progress: ConductSliceProgress, mounted: MountWorktreeResult
    ) -> ConductSliceProgress:
        left_behind = mounted.outcome is Outcome.WORKTREE_LEFT_BEHIND
        run = replace(progress.run, tree_unexpected=True) if left_behind else progress.run

        return replace(progress, run=run, conflicting_paths=(mounted.conflicting_path,), tree_left_behind=left_behind)

    def _with_the_tree_expected_from_now_on(self, progress: ConductSliceProgress) -> ConductSliceProgress:
        if not progress.run.tree_unexpected:
            return progress

        run = replace(progress.run, tree_unexpected=False)
        self._repository.write_run(repo=progress.params.repo, issue=progress.subissue.number, run=run)

        return replace(progress, run=run)

    def _blocked_by_the_worktree(self, progress: ConductSliceProgress, outcome: Outcome) -> ConductSliceResult:
        transition = self._machine.after(progress.run, outcome)
        if progress.subissue.run is None:
            self._repository.write_run(repo=progress.params.repo, issue=progress.subissue.number, run=transition.run)
        closed = self._recorded(progress, transition)

        return self._closing(closed, transition.closure)

    @staticmethod
    def _staged_work_waits_at(step: Step) -> bool:
        return step is Step.VERIFY or step is Step.OPEN_PULL_REQUEST or step is Step.AWAIT_CI

    def _rescuing_staged_work(self, progress: ConductSliceProgress) -> None:
        self._rescue.execute(
            RescueStagedWorkParams(
                worktree=progress.worktree,
                branch=progress.subissue.branch,
                message=self._pull_request.commit_message(
                    progress.subissue, round=max(progress.run.control_rounds_logged, 1)
                ),
            )
        )

    def _caught_up_before_conducting(self, progress: ConductSliceProgress) -> ConductSliceResult:
        caught_up = self._catch_up.execute(
            CatchUpBranchParams(worktree=progress.worktree, branch=progress.subissue.branch, base=progress.params.base)
        )
        if caught_up.outcome is Outcome.CONFLICTING:
            return self._blocked_by_a_catch_up_conflict(
                replace(progress, conflicting_paths=caught_up.conflicting_paths)
            )

        return self._conducting(progress)

    def _blocked_by_a_catch_up_conflict(self, progress: ConductSliceProgress) -> ConductSliceResult:
        transition = self._machine.after(progress.run, Outcome.CONFLICTING)
        closed = self._recorded(progress, transition)

        return self._closing(closed, transition.closure)

    def _prechecking(self, progress: ConductSliceProgress) -> ConductSliceResult:
        precheck = self._prechecks.execute(
            RunPrechecksParams(
                repo=progress.params.repo,
                root=progress.params.root,
                branch=progress.subissue.branch,
                base=progress.params.base,
                subissue=progress.subissue,
                parent=progress.parent,
            )
        )
        if precheck.outcome is not PrecheckOutcome.CLEAR:
            return self._halted_by(progress, precheck)

        return self._mounting(progress, then=self._reading_the_sources)

    def _reading_the_sources(self, progress: ConductSliceProgress) -> ConductSliceResult:
        checked = self._check_sources.execute(
            CheckSourcesParams(
                worktree=progress.worktree,
                sources=progress.parent.sources,
                designs=progress.subissue.designs_under(progress.parent),
            )
        )
        if checked.outcome is not PrecheckOutcome.CLEAR:
            return self._halted_by(progress, checked)

        marked = self._marked_in_progress(progress)
        arrived = self._machine.after(marked.run, Outcome.DONE).run

        return self._conducting(replace(marked, run=arrived))

    def _halted_by(self, progress: ConductSliceProgress, precheck: PrecheckResult) -> ConductSliceResult:
        if precheck.reason is not None:
            self._repository.write_precheck_reason(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                outcome=precheck.outcome,
                reason=precheck.reason,
            )

        return self._ending(progress, Halt.PRECHECKS_BLOCKED, precheck=precheck)

    def _marked_in_progress(self, progress: ConductSliceProgress) -> ConductSliceProgress:
        if progress.label is IssueLabel.IN_PROGRESS:
            return progress

        self._repository.write_label(
            repo=progress.params.repo, issue=progress.subissue.number, remove=progress.label, add=IssueLabel.IN_PROGRESS
        )

        return replace(progress, label=IssueLabel.IN_PROGRESS)

    def _conducting(self, progress: ConductSliceProgress) -> ConductSliceResult:
        self._record_start.execute(
            RecordStartParams(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                slice_id=progress.subissue.slice_id.canonical,
                run=progress.run,
                spend=progress.spend,
                feature_slice=self._feature_slice_of(params=progress.params, subissue=progress.subissue),
            )
        )
        while True:
            stepped = self._stepping(progress)
            if isinstance(stepped, HaltedSlice):
                return self._ending(stepped.progress, stepped.halt)
            transition = self._machine.after(
                stepped.progress.run,
                stepped.outcome,
                call_died=stepped.call_died,
                verdict_recorded=stepped.verdict_recorded,
            )
            progress = self._recorded(stepped.progress, transition)
            if transition.closure.state is not RunState.OPEN:
                return self._closing(progress, transition.closure)
            if transition.wait_seconds > 0:
                progress = self._waiting(progress, transition.wait_seconds)
                if self._budgets.wait_exhausted(progress.waited_seconds, step=progress.run.step):
                    return self._exhausted(progress)

    def _exhausted(self, progress: ConductSliceProgress) -> ConductSliceResult:
        if progress.run.step is Step.AWAIT_MERGE:
            self._repository.flag_unmerged_pull_request(
                repo=progress.params.repo, issue=progress.subissue.number, pull_request=self._pull_request_of(progress)
            )

        return self._ending(progress, Halt.WAIT_EXHAUSTED)

    def _stepping(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        match progress.run.step:
            case Step.MOUNT_WORKTREE:
                raise ImpossibleTransitionError(
                    f"the run of {progress.subissue.slice_id.canonical} reached the loop before mounting its worktree"
                )
            case Step.UNDERSTAND:
                raise ImpossibleTransitionError(
                    f"the run of {progress.subissue.slice_id.canonical} is at a step this program no longer runs"
                )
            case Step.IMPLEMENT | Step.RUN_CONTROLS | Step.VERIFY:
                return self._stepping_while_producing(progress, progress.run.step)
            case Step.OPEN_PULL_REQUEST | Step.AWAIT_CI | Step.CATCH_UP | Step.AWAIT_MERGE:
                return self._stepping_while_delivering(progress, progress.run.step)

    def _stepping_while_producing(
        self,
        progress: ConductSliceProgress,
        step: Literal[Step.IMPLEMENT, Step.RUN_CONTROLS, Step.VERIFY],
    ) -> SteppedSlice:
        match step:
            case Step.IMPLEMENT:
                return self._implementing(progress)
            case Step.RUN_CONTROLS:
                return self._running_the_controls(progress)
            case Step.VERIFY:
                return self._judging(progress)

    def _stepping_while_delivering(
        self,
        progress: ConductSliceProgress,
        step: Literal[Step.OPEN_PULL_REQUEST, Step.AWAIT_CI, Step.CATCH_UP, Step.AWAIT_MERGE],
    ) -> SteppedSlice | HaltedSlice:
        match step:
            case Step.OPEN_PULL_REQUEST:
                return self._opening_the_pull_request(progress)
            case Step.AWAIT_CI:
                return self._asking_the_ci(progress)
            case Step.CATCH_UP:
                return self._catching_up_the_branch(progress)
            case Step.AWAIT_MERGE:
                return self._asking_for_the_merge(progress)

    def _catching_up_the_branch(self, progress: ConductSliceProgress) -> SteppedSlice:
        caught_up = self._catch_up.execute(
            CatchUpBranchParams(worktree=progress.worktree, branch=progress.subissue.branch, base=progress.params.base)
        )
        if caught_up.outcome is not Outcome.CONFLICTING:
            return SteppedSlice(progress=progress, outcome=caught_up.outcome)

        return SteppedSlice(
            progress=replace(progress, conflicting_paths=caught_up.conflicting_paths), outcome=caught_up.outcome
        )

    def _implementing(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        try:
            implementation = self._implement.execute(
                ImplementSliceParams(
                    repo=progress.params.repo,
                    worktree=progress.worktree,
                    subissue=progress.subissue,
                    parent=progress.parent,
                    findings=progress.findings_of_the_last_round,
                    control_logs=progress.control_logs,
                    hygiene_refusal=progress.hygiene_refusal,
                    retry_instruction=progress.run.retry_instruction,
                    requested_changes=progress.run.requested_changes,
                    previous_call_died=progress.run.previous_call_died,
                )
            )
        except MeasuredCallError as rejection:
            discarded = self._discarding(progress, rejection)

            return self._within_budget(
                SteppedSlice(progress=discarded, outcome=Outcome.DISCARDED, call_died=True), call=rejection.spend
            )

        implemented = replace(
            progress,
            paths=implementation.paths,
            debt=implementation.left_out,
            deviations=implementation.deviations,
            spends=(*progress.spends, implementation.spend),
        )

        return self._within_budget(SteppedSlice(progress=implemented, outcome=Outcome.DONE), call=implementation.spend)

    def _running_the_controls(self, progress: ConductSliceProgress) -> SteppedSlice:
        try:
            self._stage.execute(StageSliceParams(worktree=progress.worktree, paths=progress.paths))
        except DirtyIndexError as refusal:
            return SteppedSlice(
                progress=replace(progress, control_logs=(), hygiene_refusal=str(refusal)),
                outcome=Outcome.HYGIENE_REJECTED,
            )

        round_progress = replace(progress, hygiene_refusal="")
        round_number = round_progress.run.control_round_in_progress
        ran = self._run_controls.execute(
            RunControlsParams(
                worktree=round_progress.worktree,
                controls=round_progress.parent.controls,
                logs=round_progress.params.logs,
                repo=round_progress.params.repo,
                issue=round_progress.params.issue,
                slice_id=round_progress.subissue.slice_id,
                round_in_progress=round_number,
            )
        )
        if ran.outcome is Outcome.DONE:
            self._commit.execute(
                CommitRoundParams(
                    worktree=round_progress.worktree,
                    branch=round_progress.subissue.branch,
                    message=self._pull_request.commit_message(round_progress.subissue, round=round_number),
                    repo=round_progress.params.repo,
                    issue=round_progress.subissue.number,
                    slice_id=round_progress.subissue.slice_id.canonical,
                    run=round_progress.run,
                    spend=round_progress.spend,
                    feature_slice=self._feature_slice_of(
                        params=round_progress.params, subissue=round_progress.subissue
                    ),
                    pull_request=round_progress.pull_request,
                )
            )

        return SteppedSlice(progress=replace(round_progress, control_logs=ran.red_logs), outcome=ran.outcome)

    def _judging(self, progress: ConductSliceProgress) -> SteppedSlice:
        if self._budgets.exhausted(progress.spend):
            return SteppedSlice(progress=progress, outcome=Outcome.OVER_BUDGET)

        designs = progress.subissue.designs_under(progress.parent)
        captures = self._read_captures.execute(ReadDesignCapturesParams(worktree=progress.worktree, designs=designs))
        try:
            verification = self._verify.execute(
                VerifySliceParams(
                    repo=progress.params.repo,
                    issue=progress.subissue.number,
                    worktree=progress.worktree,
                    base=f"origin/{progress.params.base}",
                    slice_id=progress.subissue.slice_id.canonical,
                    verify_round=progress.run.verify_round_in_progress,
                    prior_art=progress.parent.prior_art,
                    signal=progress.subissue.signal,
                    excludes=progress.subissue.excludes,
                    replaces=progress.subissue.replaces,
                    criteria=progress.subissue.criteria,
                    sources=progress.parent.sources,
                    checklist=progress.chosen.checklist,
                    prior_findings=progress.findings_of_the_last_round,
                    debt=progress.debt,
                    decisions=progress.subissue.decisions_under(progress.parent),
                    deviations=progress.deviations,
                    designs=designs,
                    captures=captures,
                    compares_with_the_last_verification=progress.judged_in_this_invocation,
                )
            )
        except UnchangedDiffError:
            return SteppedSlice(progress=progress, outcome=Outcome.UNCHANGED)
        except MeasuredCallError as rejection:
            discarded = self._discarding(progress, rejection)

            return self._within_budget(
                SteppedSlice(progress=discarded, outcome=Outcome.DISCARDED), call=rejection.spend
            )

        judged = replace(
            progress,
            spends=(*progress.spends, verification.spend),
            verdicts=(*progress.verdicts, verification.verdict),
        )
        stepped = SteppedSlice(
            progress=judged, outcome=Outcome.of_the_verdict(verification.verdict), verdict_recorded=True
        )
        if verification.verdict.ruling is Ruling.PASS:
            return stepped

        return self._within_budget(stepped, call=verification.spend)

    def _within_budget(self, stepped: SteppedSlice, *, call: HarnessSpend | None) -> SteppedSlice:
        exhaustion = self._budgets.cost_exhausted(call=call, total=stepped.progress.spend)

        return replace(stepped, outcome=Outcome.of_the_cost_exhaustion(exhaustion, otherwise=stepped.outcome))

    @staticmethod
    def _discarding(progress: ConductSliceProgress, rejection: MeasuredCallError) -> ConductSliceProgress:
        spends = progress.spends if rejection.spend is None else (*progress.spends, rejection.spend)

        return replace(
            progress,
            spends=spends,
            run=replace(progress.run, discarded_call=DiscardedCall.of_the_rejection(progress.run.step, rejection)),
        )

    def _opening_the_pull_request(self, progress: ConductSliceProgress) -> SteppedSlice:
        designs = progress.subissue.designs_under(progress.parent)
        self._mount_comparison.execute(
            MountComparisonParams(
                worktree=progress.worktree,
                designs=designs,
                captures=self._read_captures.execute(
                    ReadDesignCapturesParams(worktree=progress.worktree, designs=designs)
                ),
            )
        )
        opened = self._deliver.execute(
            DeliverSliceParams(
                worktree=progress.worktree,
                repo=progress.params.repo,
                branch=progress.subissue.branch,
                base=progress.params.base,
                title=self._pull_request.title(progress.subissue),
                body=self._pull_request.body(
                    progress.subissue,
                    debt=progress.debt,
                    findings=progress.findings_of_the_last_round,
                    deviations=progress.deviations,
                ),
            )
        )

        return SteppedSlice(
            progress=replace(
                progress,
                pull_request=opened,
                comparison=DesignCapturesDirectory.comparison_page_of(progress.worktree, designs),
            ),
            outcome=Outcome.DONE,
        )

    def _asking_the_ci(self, progress: ConductSliceProgress) -> SteppedSlice:
        opened = self._pull_request_of(progress)
        result = self._read_ci.execute(ReadCiStatusParams(repo=progress.params.repo, pull_request=opened))
        asked = replace(progress, pull_request=opened)
        if result.outcome is not Outcome.INDETERMINATE:
            return SteppedSlice(progress=asked, outcome=result.outcome)

        return SteppedSlice(
            progress=replace(asked, ci_indeterminate_cause=result.indeterminate_cause), outcome=result.outcome
        )

    def _asking_for_the_merge(self, progress: ConductSliceProgress) -> SteppedSlice | HaltedSlice:
        opened = self._pull_request_of(progress)
        asked = replace(progress, pull_request=opened)
        result = self._read_pull_request.execute(
            ReadPullRequestStatusParams(
                repo=progress.params.repo, pull_request=opened, last_reviewed_id=progress.run.last_reviewed_id
            )
        )

        match result.state:
            case PullRequestState.MERGED:
                return SteppedSlice(progress=asked, outcome=Outcome.DONE)
            case PullRequestState.OPEN:
                if not result.requested_changes:
                    return SteppedSlice(progress=asked, outcome=Outcome.PENDING)

                run = replace(
                    asked.run, last_reviewed_id=result.last_reviewed_id, requested_changes=result.requested_changes
                )

                return SteppedSlice(progress=replace(asked, run=run), outcome=Outcome.CHANGES_REQUESTED)
            case PullRequestState.CLOSED:
                return HaltedSlice(progress=asked, halt=Halt.PULL_REQUEST_CLOSED)

    def _pull_request_of(self, progress: ConductSliceProgress) -> int:
        if progress.pull_request is not None:
            return progress.pull_request

        opened = self._forum.any_pull_request(repo=progress.params.repo, branch=progress.subissue.branch)
        if opened is None:
            raise NoPullRequestError(
                f"the run of {progress.subissue.slice_id.canonical} stands on `{progress.run.step}` and no pull "
                f"request of any state was found for {progress.subissue.branch}"
            )

        return opened

    @staticmethod
    def _feature_slice_of(*, params: ConductSliceParams, subissue: SubIssue) -> FeatureSlice:
        return FeatureSlice(parent=params.issue, name=subissue.slice_id.name)

    def _recorded(self, progress: ConductSliceProgress, transition: Transition) -> ConductSliceProgress:
        recorded = self._record_step.execute(
            RecordStepParams(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                slice_id=progress.subissue.slice_id.canonical,
                current=progress.run,
                label=progress.label,
                transition=transition,
                spend=progress.spend,
                feature_slice=self._feature_slice_of(params=progress.params, subissue=progress.subissue),
                pull_request=progress.pull_request,
                comparison=progress.comparison,
            )
        )

        return replace(
            progress,
            run=recorded.run,
            label=recorded.label,
            waited_seconds=self._carried(progress, stepped_to=recorded.run.step),
        )

    @staticmethod
    def _carried(progress: ConductSliceProgress, *, stepped_to: Step) -> int:
        if stepped_to is progress.run.step:
            return progress.waited_seconds

        return 0

    def _closing_a_merge_missed_between_invocations(self, params: ConductSliceParams, subissue: SubIssue) -> bool:
        run = subissue.run
        if run is None:
            return False

        opened = self._forum.any_pull_request(repo=params.repo, branch=subissue.branch)
        if (
            opened is None
            or self._forum.pull_request_state(repo=params.repo, number=opened).state is not PullRequestState.MERGED
        ):
            return False

        worktree = subissue.slice_id.worktree_under(params.root)
        self._record_closure.execute(
            RecordClosureParams(
                repo=params.repo,
                issue=subissue.number,
                slice_id=subissue.slice_id.canonical,
                name=subissue.slice_id.name,
                closure=Closure.merged(),
                run=run,
                budgets=self._budgets,
                models=self._models,
                worktree=worktree,
                worktree_retirement=self._retiring(
                    RetireWorktreeParams(root=params.root, worktree=worktree, branch=subissue.branch),
                    closure=Closure.merged(),
                    step=run.step,
                    derived=True,
                    tree_left_behind=False,
                ),
            )
        )
        self._record_step.execute(
            RecordStepParams(
                repo=params.repo,
                issue=subissue.number,
                slice_id=subissue.slice_id.canonical,
                current=run,
                label=subissue.label,
                transition=Transition(run=run, closure=Closure.merged()),
                spend=run.spend,
                feature_slice=self._feature_slice_of(params=params, subissue=subissue),
                pull_request=opened,
            )
        )
        self._repository.clear_run(repo=params.repo, issue=subissue.number)
        self._close.execute(CloseParentParams(repo=params.repo, issue=params.issue))

        return True

    @staticmethod
    def _reported_after_reconciling(unselectable: NoSliceLeftError, reconciled: int) -> NoSliceLeftError:
        error = NoSliceLeftError(f"{unselectable}; reconciled {reconciled} dangling slice(s) before giving up")
        error.dangling = unselectable.dangling

        return error

    def _waiting(self, progress: ConductSliceProgress, seconds: int) -> ConductSliceProgress:
        self._clock.sleep(seconds=seconds)

        return replace(progress, waited_seconds=progress.waited_seconds + seconds)

    def _retiring(
        self, tree: RetireWorktreeParams, *, closure: Closure, step: Step, derived: bool, tree_left_behind: bool
    ) -> WorktreeRetirement:
        closing = WorktreeRetirementPolicy.of_the_closing(closure=closure, step=step, tree_left_behind=tree_left_behind)
        if closing is not ClosingWorktree.RETIRE or not derived:
            return WorktreeRetirement.without_retiring(closing)

        return self._retire.execute(tree).retirement

    def _closing(self, progress: ConductSliceProgress, closure: Closure) -> ConductSliceResult:
        retirement = self._retiring(
            RetireWorktreeParams(
                root=progress.params.root, worktree=progress.worktree, branch=progress.subissue.branch
            ),
            closure=closure,
            step=progress.run.step,
            derived=progress.params.worktree is None,
            tree_left_behind=progress.tree_left_behind,
        )
        self._record_closure.execute(
            RecordClosureParams(
                repo=progress.params.repo,
                issue=progress.subissue.number,
                slice_id=progress.subissue.slice_id.canonical,
                name=progress.subissue.slice_id.name,
                closure=closure,
                run=progress.run,
                budgets=self._budgets,
                models=self._models,
                ci_indeterminate_cause=progress.ci_indeterminate_cause,
                conflicting_paths=progress.conflicting_paths,
                worktree=progress.worktree,
                worktree_retirement=retirement,
            )
        )
        if closure.state is RunState.MERGED:
            self._repository.clear_run(repo=progress.params.repo, issue=progress.subissue.number)
            self._close.execute(CloseParentParams(repo=progress.params.repo, issue=progress.params.issue))

        return self._ending(progress, Halt.RUN_CLOSED, closure=closure, retirement=retirement)

    _STILL_OPEN: ClassVar[Closure] = Closure.open()

    @staticmethod
    def _ending(
        progress: ConductSliceProgress,
        halt: Halt,
        *,
        closure: Closure = _STILL_OPEN,
        precheck: PrecheckResult | None = None,
        retirement: WorktreeRetirement = WorktreeRetirement.NOT_MOUNTED,
    ) -> ConductSliceResult:
        return ConductSliceResult(
            halt=halt,
            closure=closure,
            step=progress.run.step,
            precheck=precheck,
            pull_request=progress.pull_request,
            worktree=progress.worktree,
            worktree_retirement=retirement,
            conflicting_path=progress.conflicting_paths[0] if closure.reason is ClosingReason.WORKTREE else "",
        )
