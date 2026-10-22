from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.domain.issue_state import IssueState
from slice_runner.infrastructure.contract_model import ContractModel


class GhSubissuesSummaryPayload(ContractModel):
    completed: int
    percent_completed: int = Field(alias="percentCompleted")
    total: int


class GhParentViewPayload(ContractModel):
    body: str
    subissues_summary: GhSubissuesSummaryPayload = Field(alias="subIssuesSummary")
    state: IssueState

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable parent issue", UnreadableIssueError)
