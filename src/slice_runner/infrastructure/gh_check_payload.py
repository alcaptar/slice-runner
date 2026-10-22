from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import UnreadableCiError
from slice_runner.infrastructure.contract_model import ContractModel


class GhCheckPayload(ContractModel):
    name: str
    bucket: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable check", UnreadableCiError)
