from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.sub_issue import SubIssue


class PullRequestWriter(ABC):
    @abstractmethod
    def title(self, subissue: SubIssue) -> str: ...

    @abstractmethod
    def commit_message(self, subissue: SubIssue, *, round: int) -> str: ...

    @abstractmethod
    def body(
        self,
        subissue: SubIssue,
        *,
        debt: tuple[str, ...],
        findings: tuple[Finding, ...],
        deviations: tuple[str, ...],
    ) -> str: ...
