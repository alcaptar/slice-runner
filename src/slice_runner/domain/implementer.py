from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.implementation import Implementation


class Implementer(ABC):
    @abstractmethod
    def implement(self, assignment: Assignment) -> Implementation: ...
