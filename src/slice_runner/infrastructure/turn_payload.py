from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.infrastructure.turn_log import HarnessTurn


class TurnPayload(ContractModel):
    slice_id: str
    step: Step
    number: int
    tool: str
    target: str | None = None

    @classmethod
    def from_domain(cls, turn: HarnessTurn) -> Self:
        return cls(slice_id=turn.slice_id, step=turn.step, number=turn.number, tool=turn.tool, target=turn.target)
