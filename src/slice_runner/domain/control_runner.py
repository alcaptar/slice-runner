from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.control_command import ControlCommand
    from slice_runner.domain.control_outcome import ControlOutcome


class ControlRunner(ABC):
    @abstractmethod
    def run(self, command: ControlCommand, *, worktree: str, out: Path) -> ControlOutcome: ...
