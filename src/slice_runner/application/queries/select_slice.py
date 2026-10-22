from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.exceptions import NoSliceLeftError
from slice_runner.domain.slice_queue import SliceQueue

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class SelectSliceParams:
    repo: str
    issue: int
    slice_id: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class SelectSliceResult:
    subissue: SubIssue
    parent: ParentIssue
    checklist: tuple[ChecklistEntry, ...]
    dangling: tuple[SubIssue, ...] = ()


class SelectSlice:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: SelectSliceParams) -> SelectSliceResult:
        overview = self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=None)
        children = self._repository.read_children(
            repo=params.repo, parent=params.issue, expected=overview.subissue_count
        )
        dangling = SliceQueue.dangling(children)
        chosen = self._chosen(children, params, dangling=dangling)

        return SelectSliceResult(
            subissue=chosen,
            parent=self._yardstick_of(chosen, overview=overview, params=params),
            checklist=tuple(ChecklistEntry.of(child) for child in children),
            dangling=dangling,
        )

    def _chosen(
        self, children: tuple[SubIssue, ...], params: SelectSliceParams, *, dangling: tuple[SubIssue, ...]
    ) -> SubIssue:
        if params.slice_id is None:
            next_in_line = SliceQueue.next_in_line(children)
            if next_in_line is not None:
                return next_in_line

            raise self._none_left(
                f"none of the {len(children)} slice(s) of issue {params.issue} can be run: "
                f"every one is closed, blocked or aborted; reopen a blocked one with `slice-runner retry`",
                dangling=dangling,
            )

        named = SliceQueue.find(children, params.slice_id)
        if named is None:
            raise self._none_left(
                f"slice {params.slice_id} does not exist among the {len(children)} slice(s) of issue {params.issue}",
                dangling=dangling,
            )
        if SliceQueue.runnable(named):
            return named
        if SliceQueue.blocked(named):
            raise self._none_left(
                f"slice {params.slice_id} of issue {params.issue} is blocked and waits for `slice-runner retry`",
                dangling=dangling,
            )

        raise self._none_left(
            f"slice {params.slice_id} of issue {params.issue} cannot be run: it is closed, blocked or aborted",
            dangling=dangling,
        )

    @staticmethod
    def _none_left(message: str, *, dangling: tuple[SubIssue, ...]) -> NoSliceLeftError:
        error = NoSliceLeftError(message)
        error.dangling = dangling

        return error

    def _yardstick_of(self, chosen: SubIssue, *, overview: ParentIssue, params: SelectSliceParams) -> ParentIssue:
        if chosen.repo is None:
            return overview

        return self._repository.read_parent(repo=params.repo, issue=params.issue, slice_repo=chosen.repo)
