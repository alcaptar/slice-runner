from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessCall:
    coordinates: SliceCoordinates
    step: Step
    session: str


class CallTrace(ABC):
    @abstractmethod
    def record(self, call: HarnessCall) -> None: ...

    @abstractmethod
    def sessions_of(self, *, repo: str, issue: int, slice_id: str, step: Step) -> tuple[str, ...]: ...

    @abstractmethod
    def calls_of(self, *, repo: str, issue: int, slice_id: str) -> tuple[HarnessCall, ...]: ...
