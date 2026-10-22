from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_diff import SliceDiff


class DiffReader(ABC):
    @abstractmethod
    def read(self, *, worktree: str, base: str) -> SliceDiff: ...

    @abstractmethod
    def dirty(self, *, worktree: str) -> tuple[str, ...]: ...
