from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventLog(ABC):
    @abstractmethod
    def emit(self, event: Event) -> None: ...
