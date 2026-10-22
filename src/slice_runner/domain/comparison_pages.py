from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures


class ComparisonPages(ABC):
    @abstractmethod
    def write(
        self, *, worktree: str, designs: tuple[Design, ...], captures: DesignCaptures | MissingDesignCaptures
    ) -> None: ...
