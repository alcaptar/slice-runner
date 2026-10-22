from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.outcome import Outcome

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches


@dataclass(frozen=True, kw_only=True, slots=True)
class CatchUpBranchParams:
    worktree: str
    branch: str
    base: str


@dataclass(frozen=True, kw_only=True, slots=True)
class CatchUpBranchResult:
    outcome: Outcome
    conflicting_paths: tuple[str, ...] = field(default=())


class CatchUpBranch:
    def __init__(self, *, branches: Branches) -> None:
        self._branches = branches

    def execute(self, params: CatchUpBranchParams) -> CatchUpBranchResult:
        caught_up = self._branches.catch_up(worktree=params.worktree, name=params.branch, base=params.base)

        return CatchUpBranchResult(
            outcome=Outcome.of_the_catch_up(caught_up.outcome), conflicting_paths=caught_up.conflicting_paths
        )
