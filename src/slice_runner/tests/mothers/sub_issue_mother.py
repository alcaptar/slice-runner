from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.domain.sub_issue import SubIssue
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run


class SubIssueMother:
    OTHER_REPO: ClassVar[str] = "alcaptar/otro-repo"

    @staticmethod
    def pending() -> SubIssue:
        return SubIssue(
            number=45,
            slice_id=SliceIdentity(ordinal=5, name="prechecks-deterministas"),
            summary="comprobar antes de tocar codigo",
            title="slice-05 (prechecks-deterministas): comprobar antes de tocar codigo",
            state=IssueState.OPEN,
            repo=None,
            intention="hoy nada evita reimplementar una slice ya entregada",
            criteria=(
                "antes de tocar codigo comprueba que la subissue no este ya cerrada",
                "cada precheck falla con un motivo distinguible, no con un booleano",
            ),
            decisions=("el padre decide el reparto de responsabilidades entre las capas",),
            signal="exenta - este repo no despliega",
            excludes="",
            replaces="",
            run=None,
            label=IssueLabel.PENDING,
        )

    @staticmethod
    def closed() -> SubIssue:
        return replace(SubIssueMother.pending(), state=IssueState.CLOSED)

    @staticmethod
    def dangling() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            state=IssueState.CLOSED,
            run=RunMother.awaiting_merge(),
            label=IssueLabel.AWAITING_MERGE,
        )

    @staticmethod
    def dangling_with_its_label_already_removed_by_hand() -> SubIssue:
        return replace(SubIssueMother.dangling(), label=None)

    @staticmethod
    def carrying(label: IssueLabel) -> SubIssue:
        return replace(SubIssueMother.pending(), label=label)

    @staticmethod
    def blocked(label: IssueLabel, run: Run) -> SubIssue:
        return replace(SubIssueMother.pending(), label=label, run=run)

    @staticmethod
    def unlabelled() -> SubIssue:
        return replace(SubIssueMother.pending(), label=None)

    @staticmethod
    def without_decisions() -> SubIssue:
        return replace(SubIssueMother.pending(), decisions=())

    @staticmethod
    def exempt_from_decisions() -> SubIssue:
        return replace(SubIssueMother.pending(), decisions=("ninguna - la slice no decide nada de diseno",))

    @staticmethod
    def without_a_declared_intention() -> SubIssue:
        return replace(SubIssueMother.pending(), intention="")

    @staticmethod
    def without_a_recognizable_spec() -> SubIssue:
        return replace(SubIssueMother.pending(), intention="", criteria=())

    @staticmethod
    def with_a_single_criterion() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            criteria=("cada precheck falla con un motivo distinguible, no con un booleano",),
        )

    @staticmethod
    def of_a_second_slice() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            number=46,
            slice_id=SliceIdentity(ordinal=6, name="pausa-de-alineacion"),
            summary="el entendimiento se escribe siempre",
            title="slice-06 (pausa-de-alineacion): el entendimiento se escribe siempre",
        )

    @staticmethod
    def of_another_repo() -> SubIssue:
        return replace(SubIssueMother.of_a_second_slice(), repo=SubIssueMother.OTHER_REPO)

    @staticmethod
    def declaring_an_exclusion() -> SubIssue:
        return replace(SubIssueMother.pending(), excludes="el panel de grafana que consume esta serie")

    @staticmethod
    def declaring_a_replacement() -> SubIssue:
        return replace(SubIssueMother.pending(), replaces="si - el adaptador viejo; apagando el flag")

    @staticmethod
    def carrying_a_user_story() -> SubIssue:
        return replace(
            SubIssueMother.pending(),
            slice_id=SliceIdentity(ordinal=5, name="prechecks-deterministas", user_story="PROJ-1234"),
            title="PROJ-1234 slice-05 (prechecks-deterministas): comprobar antes de tocar codigo",
        )

    @staticmethod
    def naming_designs(*names: str) -> SubIssue:
        return replace(SubIssueMother.pending(), design_names=names)
