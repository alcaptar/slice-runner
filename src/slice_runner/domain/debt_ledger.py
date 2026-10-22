from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.debt_entry import DebtEntry
    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class DebtDeclaration:
    left_out: tuple[str, ...]


class DebtLedger(ABC):
    @abstractmethod
    def record(self, entry: DebtEntry) -> None: ...

    @abstractmethod
    def declarations_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[DebtDeclaration, ...]: ...
