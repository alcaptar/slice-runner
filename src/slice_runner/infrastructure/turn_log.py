from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessTurn:
    slice_id: str
    step: Step
    number: int
    tool: str
    target: str | None


class TurnLog(ABC):
    @abstractmethod
    def observe(self, turn: HarnessTurn) -> None: ...
