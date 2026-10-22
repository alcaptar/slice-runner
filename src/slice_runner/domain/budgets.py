from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.cost_exhaustion import CostExhaustion
from slice_runner.domain.waiting_on import WaitingOn

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Budgets:
    control_retries: int = 2
    hygiene_retries: int = 2
    verify_retries: int = 2
    ci_retries: int = 1
    catch_up_retries: int = 3
    indeterminate_ticks: int = 10
    seconds_between_ticks: int = 30
    seconds_between_follow_reads: int = 5
    ci_wait_seconds: int = 1800
    person_wait_seconds: int = 28800
    process_timeout_seconds: int = 3600
    slice_cost_usd: float = 50.0
    gh_retries: int = 3
    seconds_between_gh_retries: int = 2
    sources_max_chars: int = 200_000

    def sources_exceed(self, total_chars: int) -> bool:
        return total_chars > self.sources_max_chars

    def wait_exhausted(self, waited_seconds: int, *, step: Step) -> bool:
        return waited_seconds >= self.waiting_room_of(step)

    def waiting_room_of(self, step: Step) -> int:
        if WaitingOn.of_the_step(step) is WaitingOn.PERSON:
            return self.person_wait_seconds

        return self.ci_wait_seconds

    def exhausted(self, total: HarnessSpend) -> bool:
        return total.cost_usd >= self.slice_cost_usd

    def cost_exhausted(self, *, call: HarnessSpend | None, total: HarnessSpend) -> CostExhaustion:
        if call is None or not call.measured:
            return CostExhaustion.CALL_UNMEASURED
        if self.exhausted(total):
            return CostExhaustion.TOTAL_EXCEEDED

        return CostExhaustion.WITHIN_BUDGET
