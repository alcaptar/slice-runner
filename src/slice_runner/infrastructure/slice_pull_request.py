from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.pull_request_writer import PullRequestWriter
from slice_runner.infrastructure.pull_request_body import PullRequestBody
from slice_runner.infrastructure.slice_commit_message import SliceCommitMessage

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.sub_issue import SubIssue


class SlicePullRequest(PullRequestWriter):
    COMMIT_TYPE: ClassVar[str] = "feat"

    _ONE_CRITERION: ClassVar[str] = (
        "el criterio de aceptacion de la subissue #{subissue} queda cumplido, su detalle vive en el issue"
    )
    _MANY_CRITERIA: ClassVar[str] = (
        "los {count} criterios de aceptacion de la subissue #{subissue} quedan cumplidos, su detalle vive en el issue"
    )

    def title(self, subissue: SubIssue) -> str:
        conventional = self._conventional_title(subissue)
        if subissue.slice_id.user_story is None:
            return conventional

        return f"{subissue.slice_id.canonical} {conventional}"

    def commit_message(self, subissue: SubIssue, *, round: int) -> str:
        return SliceCommitMessage(subject=self._conventional_title(subissue), round=round).rendered()

    @classmethod
    def _conventional_title(cls, subissue: SubIssue) -> str:
        return f"{cls.COMMIT_TYPE}({subissue.slice_id.name}): {subissue.summary}"

    def body(
        self,
        subissue: SubIssue,
        *,
        debt: tuple[str, ...],
        findings: tuple[Finding, ...],
        deviations: tuple[str, ...],
    ) -> str:
        return PullRequestBody(
            intention=subissue.intention,
            criteria=self._criteria_confirmation(subissue),
            debt=debt,
            findings=findings,
            deviations=deviations,
            subissue=subissue.number,
        ).rendered()

    @classmethod
    def _criteria_confirmation(cls, subissue: SubIssue) -> tuple[str, ...]:
        count = len(subissue.criteria)
        confirmation = cls._ONE_CRITERION if count == 1 else cls._MANY_CRITERIA

        return (confirmation.format(count=count, subissue=subissue.number),)
