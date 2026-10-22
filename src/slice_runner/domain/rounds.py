from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.round_budget import RoundBudget
from slice_runner.domain.run import Run
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets


@dataclass(frozen=True, kw_only=True, slots=True)
class Rounds:
    controls: RoundBudget
    hygiene: RoundBudget
    judge: RoundBudget
    ci: RoundBudget
    ci_indeterminate: RoundBudget
    catch_up: RoundBudget

    @classmethod
    def of(cls, run: Run, budgets: Budgets) -> Rounds:
        return cls(
            controls=RoundBudget(used=run.control_retries, limit=budgets.control_retries),
            hygiene=RoundBudget(used=run.hygiene_retries, limit=budgets.hygiene_retries),
            judge=RoundBudget(used=run.verify_retries, limit=budgets.verify_retries),
            ci=RoundBudget(used=run.ci_retries, limit=budgets.ci_retries),
            ci_indeterminate=RoundBudget(used=run.indeterminate_ticks, limit=budgets.indeterminate_ticks),
            catch_up=RoundBudget(used=run.catch_up_retries, limit=budgets.catch_up_retries),
        )

    @classmethod
    def untouched(cls, budgets: Budgets) -> Rounds:
        return cls.of(Run(step=Step.MOUNT_WORKTREE), budgets)
