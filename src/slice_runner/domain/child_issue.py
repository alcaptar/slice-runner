from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.issue_state import IssueState
    from slice_runner.domain.slice_identity import SliceIdentity


@dataclass(frozen=True, kw_only=True, slots=True)
class ChildIssue:
    number: int
    slice_id: SliceIdentity
    state: IssueState
