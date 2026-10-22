from __future__ import annotations

from typing import Self

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel


class DiscardedCallPayload(ContractModel):
    step: Step
    cause: DiscardCause
    reason: str

    @classmethod
    def from_domain(cls, discarded: DiscardedCall) -> Self:
        return cls(step=discarded.step, cause=discarded.cause, reason=discarded.reason)

    def to_domain(self) -> DiscardedCall:
        return DiscardedCall(step=self.step, cause=self.cause, reason=self.reason)
