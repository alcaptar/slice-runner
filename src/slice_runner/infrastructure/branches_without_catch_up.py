from __future__ import annotations

from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branches import Branches


class BranchesWithoutCatchUp(Branches):
    def __init__(self, *, branches: Branches) -> None:
        self._branches = branches

    def commits_behind_remote(self, *, worktree: str, base: str) -> int:
        return self._branches.commits_behind_remote(worktree=worktree, base=base)

    def catch_up(self, *, worktree: str, name: str, base: str) -> BranchCatchUp:
        return BranchCatchUp.caught_up()
