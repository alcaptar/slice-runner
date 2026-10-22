from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_queue import SliceQueue

if TYPE_CHECKING:
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class CloseParentParams:
    repo: str
    issue: int


class CloseParent:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: CloseParentParams) -> None:
        overview = self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=None)
        if overview.state is IssueState.CLOSED or overview.subissue_count == 0:
            return

        children = self._repository.read_children(
            repo=params.repo, parent=params.issue, expected=overview.subissue_count
        )
        if not SliceQueue.all_delivered(children):
            return

        self._repository.close_parent(repo=params.repo, issue=params.issue, subissue_count=overview.subissue_count)
