from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.harness_spend import HarnessSpend

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceStatus:
    sub_issue: SubIssue
    pull_request: int | None
    record: ClosedSliceRecord | None = None
    spend: HarnessSpend = field(default_factory=HarnessSpend.nothing)

    @property
    def shown_cost_usd(self) -> float | None:
        if self.sub_issue.run is not None:
            return self.spend.cost_usd if self.spend.measured else None
        if self.record is not None and self.record.spend is not None:
            return self.record.spend.cost_usd

        return None
