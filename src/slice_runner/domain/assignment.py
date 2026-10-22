from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.controls import Controls
    from slice_runner.domain.design import Design
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.requested_change import RequestedChange
    from slice_runner.domain.source import Source


@dataclass(frozen=True, kw_only=True, slots=True)
class Assignment:
    issue: int
    slice_id: str
    repo: str
    worktree: str
    intention: str
    prior_art: str
    criteria: tuple[str, ...]
    signal: str
    excludes: str
    replaces: str
    sources: tuple[Source, ...]
    controls: Controls
    findings: tuple[Finding, ...] = ()
    control_logs: tuple[Path, ...] = ()
    hygiene_refusal: str = ""
    decisions: tuple[str, ...] = ()
    retry_instruction: str = ""
    requested_changes: tuple[RequestedChange, ...] = ()
    dirty_worktree_files: tuple[str, ...] = ()
    staged_files: tuple[str, ...] = ()
    designs: tuple[Design, ...] = ()
