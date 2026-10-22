from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.exceptions import UnreadableFindingsError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.verdict_payload import FindingPayload

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class PublishedFindingPayload(ContractModel):
    id: str
    finding: FindingPayload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the veto findings block holds a malformed finding", UnreadableFindingsError)

    @classmethod
    def from_domain(cls, *, id: str, finding: Finding) -> Self:
        return cls.model_validate({"id": id, "finding": FindingPayload.from_domain(finding).to_contract()})

    def to_domain(self) -> Finding:
        return self.finding.to_domain()
