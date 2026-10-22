from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.declared_debt import DeclaredDebt
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.findings_history import FindingsHistory
    from slice_runner.domain.issue_label import IssueLabel
    from slice_runner.domain.order import Order
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.precheck_outcome import PrecheckOutcome
    from slice_runner.domain.run import Run
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.worktree_retirement import WorktreeRetirement


class RunRepository(ABC):
    @abstractmethod
    def read_parent(self, *, repo: str, issue: int, slice_repo: str | None) -> ParentIssue: ...

    @abstractmethod
    def read_children(self, *, repo: str, parent: int, expected: int) -> tuple[SubIssue, ...]: ...

    @abstractmethod
    def read_subissue(self, *, repo: str, issue: int) -> SubIssue: ...

    @abstractmethod
    def mark_order(self, *, repo: str, issue: int, order: Order, text: str) -> None: ...

    @abstractmethod
    def write_run(self, *, repo: str, issue: int, run: Run) -> None: ...

    @abstractmethod
    def clear_run(self, *, repo: str, issue: int) -> None: ...

    @abstractmethod
    def mark_reset(self, *, repo: str, issue: int, branch: str, at: datetime) -> None: ...

    @abstractmethod
    def write_label(self, *, repo: str, issue: int, remove: IssueLabel | None, add: IssueLabel) -> None: ...

    @abstractmethod
    def remove_label(self, *, repo: str, issue: int, remove: IssueLabel) -> None: ...

    @abstractmethod
    def flag_unmerged_pull_request(self, *, repo: str, issue: int, pull_request: int) -> None: ...

    @abstractmethod
    def write_precheck_reason(self, *, repo: str, issue: int, outcome: PrecheckOutcome, reason: str) -> None: ...

    @abstractmethod
    def close_parent(self, *, repo: str, issue: int, subissue_count: int) -> None: ...

    @abstractmethod
    def publish_findings(self, *, repo: str, issue: int, history: FindingsHistory, debt: DeclaredDebt) -> None: ...

    @abstractmethod
    def publish_catch_up_conflict(self, *, repo: str, issue: int, paths: tuple[str, ...]) -> None: ...

    @abstractmethod
    def publish_kept_worktree(self, *, repo: str, issue: int, path: str, retirement: WorktreeRetirement) -> None: ...

    @abstractmethod
    def find_finding(self, *, repo: str, issue: int, finding_id: str) -> Finding | None: ...
