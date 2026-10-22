from __future__ import annotations

from abc import ABC, abstractmethod


class LiveRuns(ABC):
    @abstractmethod
    def command_lines(self) -> tuple[str, ...]: ...
