from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.domain.issue_label import IssueLabel
    from slice_runner.domain.issue_state import IssueState
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.run import Run
    from slice_runner.domain.slice_identity import SliceIdentity


@dataclass(frozen=True, kw_only=True, slots=True)
class SubIssue:
    number: int
    slice_id: SliceIdentity
    summary: str
    title: str
    state: IssueState
    repo: str | None
    intention: str
    criteria: tuple[str, ...]
    decisions: tuple[str, ...]
    signal: str
    excludes: str
    replaces: str
    run: Run | None
    label: IssueLabel | None
    design_names: tuple[str, ...] = ()

    @property
    def branch(self) -> str:
        return self.slice_id.branch

    def decisions_under(self, parent: ParentIssue) -> tuple[str, ...]:
        return (*parent.decisions, *self.decisions)

    def designs_under(self, parent: ParentIssue) -> tuple[Design, ...]:
        return tuple(design for design in parent.designs if design.name in self.design_names)

    def names_a_design_missing_from(self, parent: ParentIssue) -> bool:
        declared = {design.name for design in parent.designs}

        return any(name not in declared for name in self.design_names)
