from __future__ import annotations

from dataclasses import replace

from slice_runner.domain.controls import Controls
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.parent_issue import ParentIssue
from slice_runner.domain.source import Source, SourceKind
from slice_runner.tests.mothers.control_command_mother import ControlCommandMother
from slice_runner.tests.mothers.design_mother import DesignMother


class ParentIssueMother:
    @staticmethod
    def with_sources_and_controls() -> ParentIssue:
        return ParentIssue(
            intention="hoy nada evita reimplementar una slice ya entregada",
            prior_art="",
            decisions=("las decisiones de diseno viajan en la spec",),
            sources=(Source(kind=SourceKind.DOC, path="CLAUDE.md"),),
            controls=Controls(commands=(ControlCommandMother.lint(),), exemption_reason=None),
            subissue_count=1,
            state=IssueState.OPEN,
        )

    @staticmethod
    def already_closed() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), state=IssueState.CLOSED)

    @staticmethod
    def with_no_subissues() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), subissue_count=0)

    @staticmethod
    def with_two_controls() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(),
            controls=Controls(
                commands=(
                    ControlCommandMother.lint(),
                    ControlCommandMother.tests(),
                ),
                exemption_reason=None,
            ),
        )

    @staticmethod
    def of_two_slices() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), subissue_count=2)

    @staticmethod
    def without_sources() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), sources=())

    @staticmethod
    def without_controls() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(), controls=Controls(commands=(), exemption_reason=None)
        )

    @staticmethod
    def without_decisions() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), decisions=())

    @staticmethod
    def exempt_from_decisions() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(), decisions=("ninguna: la feature no decide nada de diseno",)
        )

    @staticmethod
    def with_exempt_controls() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(),
            controls=Controls(commands=(), exemption_reason="la integracion continua solo publica en master"),
        )

    @staticmethod
    def declaring_two_designs() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(), designs=(DesignMother.board(), DesignMother.detail())
        )
