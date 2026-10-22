from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.harness_spend import HarnessSpend

if TYPE_CHECKING:
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.requested_change import RequestedChange
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Run:
    step: Step
    retry_instruction: str = ""
    tree_unexpected: bool = False
    previous_call_died: bool = False
    catching_up_the_branch: bool = False
    control_retries: int = 0
    hygiene_retries: int = 0
    verify_retries: int = 0
    ci_retries: int = 0
    catch_up_retries: int = 0
    indeterminate_ticks: int = 0
    verify_discards: int = 0
    implement_discards: int = 0
    control_rounds_logged: int = 0
    verify_rounds_logged: int = 0
    last_reviewed_id: int = 0
    requested_changes: tuple[RequestedChange, ...] = ()
    discarded_call: DiscardedCall | None = None
    spend: HarnessSpend = field(default_factory=HarnessSpend.nothing)

    @property
    def correcting_review(self) -> bool:
        return bool(self.requested_changes)

    @property
    def verify_round_in_progress(self) -> int:
        return self.verify_rounds_logged + 1

    @property
    def control_round_in_progress(self) -> int:
        return self.control_rounds_logged + 1

    @property
    def implement_retries(self) -> int:
        return self.control_retries + self.hygiene_retries + self.verify_retries + self.ci_retries
