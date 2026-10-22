from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.domain.issue_state import IssueState
from slice_runner.infrastructure.contract_model import ContractModel


class GhLabelPayload(ContractModel):
    id: str
    name: str
    description: str
    color: str


class GhSubIssuePayload(ContractModel):
    number: int
    title: str
    body: str
    labels: list[GhLabelPayload]
    state: IssueState

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable subissue", UnreadableIssueError)
