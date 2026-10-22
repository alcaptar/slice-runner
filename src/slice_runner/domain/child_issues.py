from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.child_issue import ChildIssue


class ChildIssues(ABC):
    @abstractmethod
    def of_parent(self, *, repo: str, parent: int) -> tuple[ChildIssue, ...]: ...
