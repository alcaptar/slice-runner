from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.closure import Closure
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.recorded_spend import RecordedSpend
    from slice_runner.domain.severity_count import SeverityCount


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSliceRecord:
    ts: datetime
    repo: str
    issue: int
    slice_id: str
    name: str
    closure: Closure
    findings: SeverityCount
    findings_of_the_last_round: SeverityCount
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    verify_discards: int
    implement_discards: int
    discarded_call: DiscardedCall | None
    ci_indeterminate_cause: CiIndeterminateCause | None
    spend: RecordedSpend | None
    variant: str | None
    models: tuple[str, ...]
    declared_debt: int | None
    diff: DiffStats | None
    budgets: dict[str, object]
    models_by_role: dict[str, object]
    effort_by_role: dict[str, object] | None

    @property
    def first_attempt(self) -> bool:
        return (
            self.closure.state is RunState.MERGED
            and self.implement_retries == 0
            and self.control_retries == 0
            and self.ci_retries == 0
        )
