from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import DirtyIndexError
from slice_runner.domain.staged_hygiene import StagedHygiene

if TYPE_CHECKING:
    from slice_runner.domain.hygiene_offence import HygieneOffence
    from slice_runner.domain.reported_path import ReportedPath
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class StageSliceParams:
    worktree: str
    paths: tuple[ReportedPath, ...]


class StageSlice:
    def __init__(self, *, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, params: StageSliceParams) -> None:
        declared = tuple(reported.path for reported in params.paths)
        self._workspace.stage(worktree=params.worktree, paths=declared)

        staged = self._workspace.staged(worktree=params.worktree)
        offences = StagedHygiene.of(staged=staged, declared=declared)
        if offences:
            raise DirtyIndexError(self._refusal(offences))

    @staticmethod
    def _refusal(offences: tuple[HygieneOffence, ...]) -> str:
        listed = ", ".join(f"{offence.path} ({offence.breach})" for offence in offences)

        return f"the staged index is not what the implementer reported: {listed}"
