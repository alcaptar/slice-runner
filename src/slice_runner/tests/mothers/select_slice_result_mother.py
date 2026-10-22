from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from slice_runner.application.queries.select_slice import SelectSliceResult
from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.run import Run
    from slice_runner.domain.sub_issue import SubIssue


class SelectSliceResultMother:
    @classmethod
    def about_to_start(
        cls,
        *,
        subissue: SubIssue | None = None,
        parent: ParentIssue | None = None,
        dangling: tuple[SubIssue, ...] = (),
    ) -> SelectSliceResult:
        return cls._of(subissue or SubIssueMother.pending(), parent=parent, dangling=dangling)

    @classmethod
    def resumed_at(
        cls,
        run: Run,
        *,
        subissue: SubIssue | None = None,
        parent: ParentIssue | None = None,
        label: IssueLabel | None = IssueLabel.IN_PROGRESS,
        dangling: tuple[SubIssue, ...] = (),
    ) -> SelectSliceResult:
        return cls._of(
            replace(subissue or SubIssueMother.pending(), run=run, label=label), parent=parent, dangling=dangling
        )

    @staticmethod
    def _of(
        subissue: SubIssue, *, parent: ParentIssue | None = None, dangling: tuple[SubIssue, ...] = ()
    ) -> SelectSliceResult:
        return SelectSliceResult(
            subissue=subissue,
            parent=parent or ParentIssueMother.with_sources_and_controls(),
            checklist=(ChecklistEntry.of(subissue),),
            dangling=dangling,
        )
