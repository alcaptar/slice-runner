from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.design_captures_directory import DesignCapturesDirectory

if TYPE_CHECKING:
    from slice_runner.domain.comparison_pages import ComparisonPages
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures


@dataclass(frozen=True, kw_only=True, slots=True)
class MountComparisonParams:
    worktree: str
    designs: tuple[Design, ...]
    captures: DesignCaptures | MissingDesignCaptures


class MountComparison:
    def __init__(self, *, pages: ComparisonPages) -> None:
        self._pages = pages

    def execute(self, params: MountComparisonParams) -> None:
        if DesignCapturesDirectory.comparison_page_of(params.worktree, params.designs) is None:
            return

        self._pages.write(worktree=params.worktree, designs=params.designs, captures=params.captures)
