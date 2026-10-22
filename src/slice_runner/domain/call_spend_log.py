from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessCallSpend:
    coordinates: SliceCoordinates
    session: str
    spend: HarnessSpend


class CallSpendLog(ABC):
    @abstractmethod
    def record(self, call: HarnessCallSpend) -> None: ...

    @abstractmethod
    def spend_of(self, sessions: tuple[str, ...]) -> HarnessSpend: ...

    @abstractmethod
    def spend_of_the_slice(self, coordinates: SliceCoordinates) -> HarnessSpend: ...
