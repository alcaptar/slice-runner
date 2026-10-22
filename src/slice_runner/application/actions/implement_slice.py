from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.assignment import Assignment
from slice_runner.domain.debt_entry import DebtEntry
from slice_runner.domain.slice_coordinates import SliceCoordinates

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.debt_ledger import DebtLedger
    from slice_runner.domain.design_capture_store import DesignCaptureStore
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.implementation import Implementation
    from slice_runner.domain.implementer import Implementer
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.requested_change import RequestedChange
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementSliceParams:
    repo: str
    worktree: str
    subissue: SubIssue
    parent: ParentIssue
    findings: tuple[Finding, ...] = ()
    control_logs: tuple[Path, ...] = ()
    hygiene_refusal: str = ""
    retry_instruction: str = ""
    requested_changes: tuple[RequestedChange, ...] = ()
    previous_call_died: bool = False


class ImplementSlice:
    def __init__(
        self,
        *,
        implementer: Implementer,
        reader: DiffReader,
        debt_ledger: DebtLedger,
        captures: DesignCaptureStore,
        workspace: Workspace,
    ) -> None:
        self._implementer = implementer
        self._reader = reader
        self._debt_ledger = debt_ledger
        self._captures = captures
        self._workspace = workspace

    def execute(self, params: ImplementSliceParams) -> Implementation:
        assignment = self._assignment(params)
        if assignment.designs:
            self._captures.clear(worktree=params.worktree)
        implementation = self._implementer.implement(assignment)
        self._debt_ledger.record(DebtEntry(coordinates=self._coordinates(params), left_out=implementation.left_out))

        return implementation

    @staticmethod
    def _coordinates(params: ImplementSliceParams) -> SliceCoordinates:
        return SliceCoordinates(
            repo=params.repo, issue=params.subissue.number, slice_id=params.subissue.slice_id.canonical_id
        )

    def _assignment(self, params: ImplementSliceParams) -> Assignment:
        return Assignment(
            issue=params.subissue.number,
            slice_id=params.subissue.slice_id.canonical,
            repo=params.repo,
            worktree=params.worktree,
            intention=params.subissue.intention,
            prior_art=params.parent.prior_art,
            criteria=params.subissue.criteria,
            signal=params.subissue.signal,
            excludes=params.subissue.excludes,
            replaces=params.subissue.replaces,
            sources=params.parent.sources,
            controls=params.parent.controls,
            findings=params.findings,
            control_logs=params.control_logs,
            hygiene_refusal=params.hygiene_refusal,
            decisions=params.subissue.decisions_under(params.parent),
            retry_instruction=params.retry_instruction,
            requested_changes=params.requested_changes,
            dirty_worktree_files=self._dirty_worktree_files(params),
            designs=params.subissue.designs_under(params.parent),
            staged_files=self._staged_files(params),
        )

    def _dirty_worktree_files(self, params: ImplementSliceParams) -> tuple[str, ...]:
        if not params.previous_call_died:
            return ()

        return self._reader.dirty(worktree=params.worktree)

    def _staged_files(self, params: ImplementSliceParams) -> tuple[str, ...]:
        if not params.retry_instruction:
            return ()

        return self._workspace.staged(worktree=params.worktree)
