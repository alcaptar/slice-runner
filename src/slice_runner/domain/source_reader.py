from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.cited_source import CitedSource
    from slice_runner.domain.design import Design
    from slice_runner.domain.source import Source


class SourceReader(ABC):
    @abstractmethod
    def read_all(
        self, *, worktree: str, sources: tuple[Source, ...], designs: tuple[Design, ...] = ()
    ) -> tuple[CitedSource, ...]: ...
