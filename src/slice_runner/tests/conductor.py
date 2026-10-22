from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock, create_autospec

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
from slice_runner.application.queries.select_slice import SelectSlice
from slice_runner.domain.branches import Branches
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.ci import Ci
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.clock import Clock
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.domain.debt_entry import DebtEntry
from slice_runner.domain.effort import Effort
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.forum import Forum
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.pull_request_writer import PullRequestWriter
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.workspace import Workspace
from slice_runner.domain.worktrees import Worktrees
from slice_runner.tests.doubles import RecordedActivityLog, RecordedCorpus, RecordedDebtLedger, RecordedSpendLog
from slice_runner.tests.mothers.branch_catch_up_mother import BranchCatchUpMother
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother, VerificationMother

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult
    from slice_runner.application.queries.select_slice import SelectSliceResult
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.event import Event
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.listed_worktree import ListedWorktree
    from slice_runner.domain.slice_identity import SliceIdentity
    from slice_runner.domain.verdict import Verdict


class Conductor:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 38
    ROOT: ClassVar[str] = ListedWorktreeMother.ROOT
    WORKTREE: ClassVar[str] = SubIssueMother.pending().slice_id.worktree_under(ROOT)
    COMMON_DIR: ClassVar[str] = "/repos/slice-runner/.git"
    BASE: ClassVar[str] = "master"
    LOGS: ClassVar[Path] = Path("/tmp/slice-runner/logs")
    PULL_REQUEST: ClassVar[int] = 61
    PID: ClassVar[int] = 48213
    TITLE: ClassVar[str] = "feat(prechecks-deterministas): comprobar antes de tocar codigo"
    BODY: ClassVar[str] = "## Intencion\nhoy nada evita reimplementar una slice ya entregada\n\nCloses #45"
    NOW: ClassVar[datetime] = datetime(2024, 1, 1, tzinfo=UTC)

    MODELS: ClassVar[RoleModels] = RoleModels(
        implement="sonnet", verify="sonnet", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH
    )
    SLICE_ID: ClassVar[str] = SubIssueMother.pending().slice_id.canonical
    SLICE_ISSUE: ClassVar[int] = SubIssueMother.pending().number

    def __init__(
        self, *, chosen: SelectSliceResult, budgets: Budgets | None = None, models: RoleModels | None = None
    ) -> None:
        self.budgets = budgets or Budgets()
        self.models = models or self.MODELS
        self.select = self._doubling(SelectSlice, execute=chosen)
        self.prechecks = self._doubling(RunPrechecks, execute=PrecheckResult(outcome=PrecheckOutcome.CLEAR))
        self.check_sources = self._doubling(CheckSources, execute=PrecheckResult(outcome=PrecheckOutcome.CLEAR))
        self.read_captures = self._doubling(ReadDesignCaptures, execute=DesignCapturesMother.none())
        self.worktrees: Mock = create_autospec(Worktrees, spec_set=True, instance=True)
        self.worktrees.listed.return_value = self._listing_of(chosen)
        self.worktrees.is_mounted.return_value = True
        self.worktrees.branch_exists.return_value = chosen.subissue.run is not None
        self.worktrees.common_dir.return_value = self.COMMON_DIR
        self.worktrees.has_uncommitted_work.return_value = False
        self.worktrees.local_only_commits.return_value = 0
        self.implement = self._doubling(ImplementSlice, execute=ImplementationMother.of_two_paths())
        self.stage = self._doubling(StageSlice, execute=None)
        self.commit = self._doubling(CommitRound, execute=None)
        self.workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        self.workspace.current_branch.return_value = SubIssueMother.pending().branch
        self.workspace.staged.return_value = ()
        self.rescue = RescueStagedWork(workspace=self.workspace)
        self.verify = self._doubling(VerifySlice, execute=VerificationMother.passing())
        self.mount_comparison = self._doubling(MountComparison, execute=None)
        self.deliver = self._doubling(DeliverSlice, execute=self.PULL_REQUEST)
        self.close = self._doubling(CloseParent, execute=None)
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        self.branches.catch_up.return_value = BranchCatchUpMother.caught_up()
        self.controls: Mock = create_autospec(ControlRunner, spec_set=True, instance=True)
        self.controls.run.return_value = ControlOutcomeMother.green()
        self.activity = RecordedActivityLog()
        self.ci: Mock = create_autospec(Ci, spec_set=True, instance=True)
        self.ci.status.return_value = CiStatus.GREEN
        self.forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        self.forum.pull_request_state.return_value = PullRequestStatusMother.merged()
        self.forum.open_pull_request.return_value = self.PULL_REQUEST
        self.forum.any_pull_request.return_value = self.PULL_REQUEST
        self.forum.reviews.return_value = ()
        self.clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        self.clock.now.return_value = self.NOW
        self.metrics: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        self.spend_log = RecordedSpendLog()
        self.corpus = RecordedCorpus()
        self.debt_ledger = RecordedDebtLedger()
        self.pull_request: Mock = create_autospec(PullRequestWriter, spec_set=True, instance=True)
        self.pull_request.title.return_value = self.TITLE
        self.pull_request.body.return_value = self.BODY
        self.events: Mock = create_autospec(EventLog, spec_set=True, instance=True)

    @classmethod
    def slice_dir(cls, slice_id: SliceIdentity) -> Path:
        return cls.LOGS / cls.REPO / str(cls.ISSUE) / slice_id.canonical

    def seed_spend(self, *, session: str, spend: HarnessSpend) -> None:
        coordinates = SliceCoordinates(
            repo=self.REPO, issue=self.SLICE_ISSUE, slice_id=CanonicalSliceId.of_text(self.SLICE_ID)
        )
        self.spend_log.record(HarnessCallSpend(coordinates=coordinates, session=session, spend=spend))

    def seed_debt(self, *, left_out: tuple[str, ...]) -> None:
        coordinates = SliceCoordinates(
            repo=self.REPO, issue=self.SLICE_ISSUE, slice_id=CanonicalSliceId.of_text(self.SLICE_ID)
        )
        self.debt_ledger.record(DebtEntry(coordinates=coordinates, left_out=left_out))

    def seed_verdict(self, *, round: int, verdict: Verdict) -> None:
        self.corpus.record(
            CorpusEntry(
                repo=self.REPO,
                issue=self.SLICE_ISSUE,
                slice_id=self.SLICE_ID,
                verify_round=round,
                session="seeded",
                diff=SliceDiffMother.of_the_slice(),
                verdict=verdict,
                prior_findings_given=0,
            )
        )

    @property
    def emitted_events(self) -> list[Event]:
        return [call.args[0] for call in self.events.emit.call_args_list]

    @property
    def closed(self) -> ClosedSlice:
        closed: ClosedSlice = self.metrics.record.call_args.args[0]

        return closed

    def conduct(self, *, worktree: str | None = None) -> ConductSliceResult:
        return self._action().execute(
            ConductSliceParams(
                repo=self.REPO,
                issue=self.ISSUE,
                root=self.ROOT,
                worktree=worktree,
                base=self.BASE,
                logs=self.LOGS,
            )
        )

    def _action(self) -> ConductSlice:
        return ConductSlice(
            use_cases=ConductSliceUseCases(
                select=self.select,
                prechecks=self.prechecks,
                mount=MountWorktree(worktrees=self.worktrees),
                retire=RetireWorktree(worktrees=self.worktrees),
                check_sources=self.check_sources,
                read_captures=self.read_captures,
                implement=self.implement,
                stage=self.stage,
                commit=self.commit,
                rescue=self.rescue,
                run_controls=RunControls(controls=self.controls, activity=self.activity),
                verify=self.verify,
                mount_comparison=self.mount_comparison,
                deliver=self.deliver,
                close=self.close,
                record_step=RecordStep(
                    repository=self.repository,
                    events=self.events,
                    clock=self.clock,
                    budgets=self.budgets,
                    pid=self.PID,
                ),
                record_closure=RecordClosure(
                    metrics=self.metrics,
                    repository=self.repository,
                    spend_log=self.spend_log,
                    corpus=self.corpus,
                    debt_ledger=self.debt_ledger,
                ),
                record_start=RecordStart(events=self.events, clock=self.clock, budgets=self.budgets, pid=self.PID),
                read_ci=ReadCiStatus(ci=self.ci, forum=self.forum),
                read_pull_request=ReadPullRequestStatus(forum=self.forum),
                catch_up=CatchUpBranch(branches=self.branches),
            ),
            ports=ConductSlicePorts(
                repository=self.repository,
                forum=self.forum,
                clock=self.clock,
                pull_request=self.pull_request,
            ),
            machine=StateMachine(budgets=self.budgets),
            budgets=self.budgets,
            models=self.models,
        )

    @classmethod
    def _listing_of(cls, chosen: SelectSliceResult) -> tuple[ListedWorktree, ...]:
        if chosen.subissue.run is None:
            return (ListedWorktreeMother.main_clone(),)

        return cls._mounted_listing()

    @classmethod
    def _mounted_listing(cls) -> tuple[ListedWorktree, ...]:
        return (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=cls.WORKTREE, branch=SubIssueMother.pending().branch),
        )

    @staticmethod
    def _doubling(use_case: type, *, execute: object) -> Mock:
        double: Mock = create_autospec(use_case, spec_set=True, instance=True)
        double.execute.return_value = execute

        return double
