from __future__ import annotations

from typing import Literal, Self

from slice_runner.domain.child_issue import ChildIssue
from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.infrastructure.gh_run_repository import GhRunRepository
from slice_runner.infrastructure.open_vocabulary_model import OpenVocabularyModel


class GhChildIssuePayload(OpenVocabularyModel):
    number: int
    title: str
    state: Literal["open", "closed"]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable subissue", UnreadableIssueError)

    def to_domain(self) -> ChildIssue:
        heading = GhRunRepository.SLICE_HEADING.match(self.title)
        if not heading:
            raise UnreadableIssueError(f"the subissue title does not open with `slice-NN (name):`: {self.title!r}")

        return ChildIssue(
            number=self.number,
            slice_id=SliceIdentity(ordinal=int(heading["ordinal"]), name=heading["name"], user_story=heading["key"]),
            state=IssueState(self.state.upper()),
        )
