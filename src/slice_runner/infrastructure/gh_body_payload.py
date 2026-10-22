from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.infrastructure.contract_model import ContractModel


class GhBodyPayload(ContractModel):
    body: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable issue body", UnreadableIssueError)
