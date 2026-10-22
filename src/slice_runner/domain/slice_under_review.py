from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.checklist_entry import ChecklistEntry
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures
    from slice_runner.domain.slice_diff import SliceDiff
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceUnderReview:
    slice_id: str
    repo: str
    issue: int
    worktree: str
    diff: SliceDiff
    prior_art: str
    signal: str
    excludes: str
    replaces: str
    criteria: tuple[str, ...]
    sources: tuple[Source, ...]
    checklist: tuple[ChecklistEntry, ...]
    prior_findings: tuple[Finding, ...]
    debt: tuple[str, ...]
    decisions: tuple[str, ...]
    deviations: tuple[str, ...]
    designs: tuple[Design, ...]
    captures: DesignCaptures | MissingDesignCaptures
