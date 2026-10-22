from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates
    from slice_runner.domain.step import Step
    from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause


@dataclass(frozen=True, kw_only=True, slots=True)
class ToolUse:
    turn: int
    tool: str
    path: str | None
    command: str | None
    failed: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessCallToolUse:
    coordinates: SliceCoordinates
    step: Step
    session: str
    uses: tuple[ToolUse, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class UnrecordedCallToolUse:
    coordinates: SliceCoordinates
    step: Step
    session: str
    cause: UnrecordedConversationCause


class ToolUseLog(ABC):
    @abstractmethod
    def record(self, call: HarnessCallToolUse) -> None: ...

    @abstractmethod
    def record_unrecorded(self, call: UnrecordedCallToolUse) -> None: ...
