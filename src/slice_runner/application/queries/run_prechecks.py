from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.prechecks import GroundSignals, Prechecks

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class RunPrechecksParams:
    repo: str
    root: str
    branch: str
    base: str
    subissue: SubIssue
    parent: ParentIssue


class RunPrechecks:
    def __init__(self, *, branches: Branches, forum: Forum) -> None:
        self._branches = branches
        self._forum = forum

    def execute(self, params: RunPrechecksParams) -> PrecheckResult:
        outcome = Prechecks.of(
            subissue=params.subissue,
            parent=params.parent,
            base_resolves_on_remote=self._base_resolves_on_remote(root=params.root, base=params.base),
            ground=GroundSignals(
                open_pull_request=self._forum.open_pull_request(repo=params.repo, branch=params.branch)
            ),
        )

        return PrecheckResult(outcome=outcome)

    def _base_resolves_on_remote(self, *, root: str, base: str) -> bool:
        try:
            self._branches.commits_behind_remote(worktree=root, base=base)
        except UnresolvableBaseError:
            return False

        return True
