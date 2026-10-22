from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject


class ToolUseRecorder(ABC):
    @abstractmethod
    def record_after(self, subject: HarnessCallSubject, *, step: Step, session: str) -> None: ...
