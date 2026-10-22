from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closed_slice import ClosedSlice
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.effort import Effort
from slice_runner.domain.role_models import RoleModels
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run
    from slice_runner.domain.worktree_retirement import WorktreeRetirement


class ClosedSliceMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 38
    WORKTREE: ClassVar[str] = "/repo/.worktrees/02-the-slice"
    SLICE_ID: ClassVar[str] = "slice-07"
    NAME: ClassVar[str] = "controles-como-puerto"
    BUDGETS: ClassVar[Budgets] = Budgets()
    MODELS: ClassVar[RoleModels] = RoleModels(
        implement="sonnet", verify="sonnet", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH
    )

    @classmethod
    def merged(cls) -> ClosedSlice:
        return cls._closed(Closure.merged())

    @classmethod
    def closed_as(cls, closure: Closure) -> ClosedSlice:
        return cls._closed(closure)

    @classmethod
    def merged_for_issue(cls, issue: int) -> ClosedSlice:
        return cls._closed(Closure.merged(), issue=issue)

    @classmethod
    def closed_as_for_issue(cls, closure: Closure, *, issue: int) -> ClosedSlice:
        return cls._closed(closure, issue=issue)

    @classmethod
    def merged_with_a_user_story_key(cls) -> ClosedSlice:
        return cls._closed(Closure.merged(), slice_id="PROJ-1234-07")

    @classmethod
    def still_open(cls) -> ClosedSlice:
        return cls._closed(Closure.open())

    @classmethod
    def merged_measuring(cls, *spends: HarnessSpend) -> ClosedSlice:
        return cls._closed(Closure.merged(), spends=spends)

    @classmethod
    def merged_measuring_nothing(cls) -> ClosedSlice:
        return cls.merged_measuring()

    @classmethod
    def vetoed_over(cls, *findings: Finding) -> ClosedSlice:
        return cls._closed(Closure.because_of(ClosingReason.JUDGE), findings=findings)

    @classmethod
    def merged_after_correcting(cls, *findings: Finding) -> ClosedSlice:
        return cls._closed(Closure.merged(), findings=findings, findings_of_the_last_round=())

    @classmethod
    def merged_after_going_back_for_every_reason(cls) -> ClosedSlice:
        return cls._closed(Closure.merged(), run=RunMother.that_went_back_for_every_reason())

    @classmethod
    def merged_discarding_because_of(cls, discarded: DiscardedCall | None) -> ClosedSlice:
        return cls._closed(
            Closure.merged(), run=replace(RunMother.that_went_back_for_every_reason(), discarded_call=discarded)
        )

    @classmethod
    def blocked_indeterminate_because_of(cls, cause: CiIndeterminateCause | None) -> ClosedSlice:
        return cls._closed(Closure.because_of(ClosingReason.CI_INDETERMINATE), ci_indeterminate_cause=cause)

    @classmethod
    def merged_leaving_out(cls, *left_out: str) -> ClosedSlice:
        return cls._closed(Closure.merged(), debt=DeclaredDebt(declared=True, left_out=left_out))

    @classmethod
    def merged_declaring_nothing_left_out(cls) -> ClosedSlice:
        return cls._closed(Closure.merged(), debt=DeclaredDebt(declared=True, left_out=()))

    @classmethod
    def merged_measuring_the_diff(cls, stats: DiffStats) -> ClosedSlice:
        return cls._closed(Closure.merged(), diff_stats=stats)

    @classmethod
    def merged_measuring_the_diff_and_spend(cls, stats: DiffStats, *spends: HarnessSpend) -> ClosedSlice:
        return cls._closed(Closure.merged(), diff_stats=stats, spends=spends)

    @classmethod
    def merged_discarding_and_measuring_the_diff(cls, discarded: DiscardedCall, stats: DiffStats) -> ClosedSlice:
        return cls._closed(Closure.merged(), run=RunMother.awaiting_merge_after_discarding(discarded), diff_stats=stats)

    @classmethod
    def merged_with_config(cls, *, budgets: Budgets | None = None, models: RoleModels | None = None) -> ClosedSlice:
        return cls._closed(Closure.merged(), budgets=budgets, models=models)

    @classmethod
    def merged_after_retrying_controls_and_ci(cls, *, control_retries: int, ci_retries: int) -> ClosedSlice:
        return cls._closed(
            Closure.merged(),
            run=RunMother.merged_after_retrying_controls_and_ci(control_retries=control_retries, ci_retries=ci_retries),
        )

    @classmethod
    def merged_with_its_worktree(cls, retirement: WorktreeRetirement) -> ClosedSlice:
        return replace(cls._closed(Closure.merged()), worktree=cls.WORKTREE, worktree_retirement=retirement)

    @classmethod
    def aborted_over_budget(cls, budgets: Budgets, *, spend: HarnessSpend | None = None) -> ClosedSlice:
        return cls._closed(
            Closure.because_of(ClosingReason.BUDGET), budgets=budgets, spends=None if spend is None else (spend,)
        )

    @classmethod
    def _closed(
        cls,
        closure: Closure,
        *,
        issue: int | None = None,
        slice_id: str | None = None,
        run: Run | None = None,
        budgets: Budgets | None = None,
        models: RoleModels | None = None,
        spends: tuple[HarnessSpend, ...] | None = None,
        findings: tuple[Finding, ...] = (),
        findings_of_the_last_round: tuple[Finding, ...] | None = None,
        ci_indeterminate_cause: CiIndeterminateCause | None = None,
        debt: DeclaredDebt | None = None,
        diff_stats: DiffStats | None = None,
    ) -> ClosedSlice:
        return ClosedSlice(
            repo=cls.REPO,
            issue=cls.ISSUE if issue is None else issue,
            slice_id=cls.SLICE_ID if slice_id is None else slice_id,
            name=cls.NAME,
            closure=closure,
            run=run or RunMother.awaiting_merge(),
            budgets=budgets or cls.BUDGETS,
            models=models or cls.MODELS,
            spends=(HarnessSpendMother.of_the_implementer_call(),) if spends is None else spends,
            findings=findings,
            findings_of_the_last_round=findings if findings_of_the_last_round is None else findings_of_the_last_round,
            ci_indeterminate_cause=ci_indeterminate_cause,
            debt=debt or DeclaredDebt.nothing(),
            diff_stats=diff_stats,
        )
