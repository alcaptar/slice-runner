from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.branch_standing import BranchStanding

if TYPE_CHECKING:
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class RescueStagedWorkParams:
    worktree: str
    branch: str
    message: str


class RescueStagedWork:
    def __init__(self, *, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, params: RescueStagedWorkParams) -> None:
        standing_on = self._workspace.current_branch(worktree=params.worktree)
        BranchStanding.of(standing_on=standing_on, declared=params.branch).raise_unless_ok(action="commit")

        if not self._workspace.staged(worktree=params.worktree):
            return

        self._workspace.commit(worktree=params.worktree, message=params.message)
