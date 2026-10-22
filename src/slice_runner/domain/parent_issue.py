from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.design import Design
    from slice_runner.domain.issue_state import IssueState
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class ParentIssue:
    intention: str
    prior_art: str
    decisions: tuple[str, ...]
    sources: tuple[Source, ...]
    controls: Controls
    subissue_count: int
    state: IssueState
    designs: tuple[Design, ...] = ()
