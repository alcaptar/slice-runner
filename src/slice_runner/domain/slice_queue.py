from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState

if TYPE_CHECKING:
    from slice_runner.domain.sub_issue import SubIssue


class SliceQueue:
    @classmethod
    def next_in_line(cls, children: tuple[SubIssue, ...]) -> SubIssue | None:
        for child in children:
            if cls.runnable(child):
                return child

        return None

    @classmethod
    def find(cls, children: tuple[SubIssue, ...], slice_id: str) -> SubIssue | None:
        for child in children:
            if child.slice_id.canonical == slice_id:
                return child

        return None

    @classmethod
    def runnable(cls, child: SubIssue) -> bool:
        return child.state is IssueState.OPEN and not cls._disqualifying(child.label)

    @classmethod
    def blocked(cls, child: SubIssue) -> bool:
        return child.state is IssueState.OPEN and cls._disqualifying(child.label)

    @classmethod
    def dangling(cls, children: tuple[SubIssue, ...]) -> tuple[SubIssue, ...]:
        return tuple(child for child in children if cls._left_dangling(child))

    @classmethod
    def all_delivered(cls, children: tuple[SubIssue, ...]) -> bool:
        return bool(children) and all(child.state is IssueState.CLOSED for child in children)

    @staticmethod
    def _left_dangling(child: SubIssue) -> bool:
        return child.state is IssueState.CLOSED and child.run is not None

    @staticmethod
    def _disqualifying(label: IssueLabel | None) -> bool:
        match label:
            case None | IssueLabel.PENDING | IssueLabel.IN_PROGRESS | IssueLabel.AWAITING_MERGE:
                return False
            case (
                IssueLabel.BLOCKED_CONTROLS
                | IssueLabel.BLOCKED_JUDGE
                | IssueLabel.BLOCKED_CI_RED
                | IssueLabel.BLOCKED_CI_INDETERMINATE
                | IssueLabel.BLOCKED_CI_CONFLICT
                | IssueLabel.BLOCKED_WORKTREE
                | IssueLabel.ABORTED_BUDGET
                | IssueLabel.ABORTED_UNMEASURED_CALL
            ):
                return True
