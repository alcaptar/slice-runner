from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.infrastructure.contract_model import ContractModel


class GhCommentPayload(ContractModel):
    body: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(body=data.get("body")),
            "gh returned a comment this program cannot read",
            UnreadableIssueError,
        )


class GhCommentsPayload(ContractModel):
    comments: tuple[dict[str, object], ...]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return readable comments", UnreadableIssueError)
