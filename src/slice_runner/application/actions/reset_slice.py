from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import NoRecognizableSpecError
from slice_runner.domain.issue_label import IssueLabel

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ResetSliceParams:
    repo: str
    subissue: SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ResetSliceResult:
    subissue: SubIssue


class ResetSlice:
    def __init__(self, *, repository: RunRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, params: ResetSliceParams) -> ResetSliceResult:
        subissue = params.subissue
        if not subissue.intention and not subissue.criteria:
            raise NoRecognizableSpecError(f"subissue #{subissue.number} carries no spec recognizable to reset")

        self._repository.clear_run(repo=params.repo, issue=subissue.number)
        if subissue.label is not IssueLabel.PENDING:
            self._repository.write_label(
                repo=params.repo, issue=subissue.number, remove=subissue.label, add=IssueLabel.PENDING
            )
        self._repository.mark_reset(
            repo=params.repo, issue=subissue.number, branch=subissue.branch, at=self._clock.now()
        )

        return ResetSliceResult(subissue=replace(subissue, run=None, label=IssueLabel.PENDING))
