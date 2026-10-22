from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.issue_state import IssueState
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ChecklistEntry:
    title: str
    state: IssueState

    @classmethod
    def of(cls, subissue: SubIssue) -> ChecklistEntry:
        return cls(title=subissue.title, state=subissue.state)
