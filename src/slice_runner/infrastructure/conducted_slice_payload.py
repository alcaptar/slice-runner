from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.halt import Halt
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.step import Step
from slice_runner.infrastructure.closed_as import ClosedAs
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.application.actions.conduct_slice import ConductSliceResult


class ConductedSlicePayload(ContractModel):
    halt: Halt
    state: ClosedAs
    step: Step
    precheck: PrecheckOutcome | None = None
    precheck_reason: str | None = None
    pull_request: int | None = None

    @classmethod
    def from_domain(cls, conducted: ConductSliceResult) -> Self:
        return cls(
            halt=conducted.halt,
            state=ClosedAs.of(conducted.closure),
            step=conducted.step,
            precheck=conducted.precheck.outcome if conducted.precheck is not None else None,
            precheck_reason=conducted.precheck.reason if conducted.precheck is not None else None,
            pull_request=conducted.pull_request,
        )
