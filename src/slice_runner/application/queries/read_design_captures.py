from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.design_captures import DesignCaptures

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_capture_store import DesignCaptureStore
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadDesignCapturesParams:
    worktree: str
    designs: tuple[Design, ...]


class ReadDesignCaptures:
    def __init__(self, *, captures: DesignCaptureStore) -> None:
        self._captures = captures

    def execute(self, params: ReadDesignCapturesParams) -> DesignCaptures | MissingDesignCaptures:
        if not params.designs:
            return DesignCaptures(captures=())

        return self._captures.read(worktree=params.worktree, designs=params.designs)
