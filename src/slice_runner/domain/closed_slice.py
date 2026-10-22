from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.worktree_retirement import WorktreeRetirement

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.closure import Closure
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.role_models import RoleModels
    from slice_runner.domain.run import Run
    from slice_runner.domain.severity import Severity


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSlice:
    repo: str
    issue: int
    slice_id: str
    name: str
    closure: Closure
    run: Run
    budgets: Budgets
    models: RoleModels
    spends: tuple[HarnessSpend, ...] = field(default=())
    findings: tuple[Finding, ...] = field(default=())
    findings_of_the_last_round: tuple[Finding, ...] = field(default=())
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    debt: DeclaredDebt = field(default=DeclaredDebt())
    diff_stats: DiffStats | None = None
    worktree: str = ""
    worktree_retirement: WorktreeRetirement = WorktreeRetirement.NOT_MOUNTED

    @property
    def spend(self) -> HarnessSpend:
        return HarnessSpend.summing(self.spends)

    def count_findings(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)

    def count_findings_of_the_last_round(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings_of_the_last_round if finding.severity is severity)
