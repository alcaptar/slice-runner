from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.findings_history import FindingsHistory
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.worktree_retirement import WorktreeRetirement

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.debt_ledger import DebtLedger
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.metrics_log import MetricsLog
    from slice_runner.domain.role_models import RoleModels
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordClosureParams:
    repo: str
    issue: int
    slice_id: str
    name: str
    closure: Closure
    run: Run
    budgets: Budgets
    models: RoleModels
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    conflicting_paths: tuple[str, ...] = field(default=())
    worktree: str = ""
    worktree_retirement: WorktreeRetirement = WorktreeRetirement.NOT_MOUNTED


class RecordClosure:
    def __init__(
        self,
        *,
        metrics: MetricsLog,
        repository: RunRepository,
        spend_log: CallSpendLog,
        corpus: Corpus,
        debt_ledger: DebtLedger,
    ) -> None:
        self._metrics = metrics
        self._repository = repository
        self._spend_log = spend_log
        self._corpus = corpus
        self._debt_ledger = debt_ledger

    def execute(self, params: RecordClosureParams) -> None:
        spend = self._spend_of(params)
        history = self._history_of(params)
        debt = self._debt_of(params)
        self._metrics.record(
            ClosedSlice(
                repo=params.repo,
                issue=params.issue,
                slice_id=params.slice_id,
                name=params.name,
                closure=params.closure,
                run=params.run,
                budgets=params.budgets,
                models=params.models,
                spends=(spend,) if spend.measured else (),
                findings=tuple(appearance.finding for appearance in history.every_appearance),
                findings_of_the_last_round=tuple(
                    appearance.finding for appearance in history.appearances_of_the_last_round
                ),
                ci_indeterminate_cause=params.ci_indeterminate_cause,
                debt=debt,
                diff_stats=self._size_of(params),
                worktree=params.worktree,
                worktree_retirement=params.worktree_retirement,
            )
        )
        if params.closure.publishes_the_findings and not history.is_empty:
            self._repository.publish_findings(repo=params.repo, issue=params.issue, history=history, debt=debt)
        if params.closure == Closure.because_of(ClosingReason.CI_CONFLICT) and params.conflicting_paths:
            self._repository.publish_catch_up_conflict(
                repo=params.repo, issue=params.issue, paths=params.conflicting_paths
            )

        if params.worktree_retirement.kept:
            self._repository.publish_kept_worktree(
                repo=params.repo, issue=params.issue, path=params.worktree, retirement=params.worktree_retirement
            )

    def _spend_of(self, params: RecordClosureParams) -> HarnessSpend:
        return self._spend_log.spend_of_the_slice(self._coordinates_of(params))

    def _size_of(self, params: RecordClosureParams) -> DiffStats | None:
        return self._corpus.size_of_the_last_verification(self._coordinates_of(params))

    def _history_of(self, params: RecordClosureParams) -> FindingsHistory:
        return FindingsHistory.of_rounds(self._corpus.rounds_of_the_slice(self._coordinates_of(params)))

    def _debt_of(self, params: RecordClosureParams) -> DeclaredDebt:
        return DeclaredDebt.of_declarations(self._debt_ledger.declarations_of_the_slice(self._coordinates_of(params)))

    @staticmethod
    def _coordinates_of(params: RecordClosureParams) -> SliceCoordinates:
        return SliceCoordinates(
            repo=params.repo, issue=params.issue, slice_id=CanonicalSliceId.of_text(params.slice_id)
        )
