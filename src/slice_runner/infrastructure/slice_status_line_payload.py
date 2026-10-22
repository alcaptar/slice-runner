from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.domain.slice_status import SliceStatus


class SliceStatusLinePayload(ContractModel):
    VERSION: ClassVar[int] = 1

    version: int
    slice_id: str
    name: str
    issue: int
    closed: bool
    label: IssueLabel | None = None
    cost_usd: float | None = None
    pull_request: int | None = None

    @classmethod
    def from_domain(cls, status: SliceStatus) -> Self:
        sub_issue = status.sub_issue

        return cls(
            version=cls.VERSION,
            slice_id=sub_issue.slice_id.canonical,
            name=sub_issue.slice_id.name,
            issue=sub_issue.number,
            closed=sub_issue.state is IssueState.CLOSED,
            label=sub_issue.label,
            cost_usd=status.shown_cost_usd,
            pull_request=status.pull_request,
        )
