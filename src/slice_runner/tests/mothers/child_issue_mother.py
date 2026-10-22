from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.domain.child_issue import ChildIssue
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_identity import SliceIdentity


class ChildIssueMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    PARENT: ClassVar[int] = 523

    @staticmethod
    def open(*, number: int = 524, ordinal: int = 1, name: str = "las-slices-pendientes-se-registran") -> ChildIssue:
        return ChildIssue(number=number, slice_id=SliceIdentity(ordinal=ordinal, name=name), state=IssueState.OPEN)

    @staticmethod
    def closed(*, number: int = 525, ordinal: int = 2) -> ChildIssue:
        return replace(ChildIssueMother.open(number=number, ordinal=ordinal), state=IssueState.CLOSED)

    @staticmethod
    def open_of_a_user_story() -> ChildIssue:
        return replace(
            ChildIssueMother.open(number=530, ordinal=1, name="x"),
            slice_id=SliceIdentity(ordinal=1, name="x", user_story="HU-123"),
        )
