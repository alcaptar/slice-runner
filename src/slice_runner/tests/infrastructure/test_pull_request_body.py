from __future__ import annotations

from slice_runner.infrastructure.pull_request_body import PullRequestBody
from slice_runner.tests.mothers.verdict_mother import FindingMother

_INTENTION = "sin esto el programa verifica y no entrega, asi que ningun run puede terminar"
_CRITERIA = (
    "stagea exactamente las rutas declaradas por el implementador",
    "nunca commitea en master ni en main",
)


class TestPullRequestBody:
    @staticmethod
    def _with_debt() -> PullRequestBody:
        return PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=("el cableado del subcomando queda para la slice-09",),
            findings=(),
            deviations=(),
            subissue=46,
        )

    @staticmethod
    def _without_debt() -> PullRequestBody:
        return PullRequestBody(
            intention=_INTENTION, criteria=_CRITERIA, debt=(), findings=(), deviations=(), subissue=46
        )

    def test_the_body_a_person_reads_carries_the_why_the_criteria_and_the_debt(self) -> None:
        assert self._with_debt().rendered() == (
            "## Intencion\n"
            "sin esto el programa verifica y no entrega, asi que ningun run puede terminar\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- stagea exactamente las rutas declaradas por el implementador\n"
            "- nunca commitea en master ni en main\n"
            "\n"
            "## Deuda aceptada\n"
            "- el cableado del subcomando queda para la slice-09\n"
            "\n"
            "Closes #46"
        )

    def test_a_slice_that_accepted_no_debt_leaves_the_section_out_instead_of_writing_none(self) -> None:
        assert self._without_debt().rendered() == (
            "## Intencion\n"
            "sin esto el programa verifica y no entrega, asi que ningun run puede terminar\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- stagea exactamente las rutas declaradas por el implementador\n"
            "- nunca commitea en master ni en main\n"
            "\n"
            "Closes #46"
        )

    def test_the_reference_that_closes_the_subissue_is_the_last_thing_github_reads(self) -> None:
        assert self._with_debt().rendered().endswith("\nCloses #46")
        assert self._without_debt().rendered().endswith("\nCloses #46")

    def test_a_finding_the_judge_approved_without_correcting_names_the_rule_it_broke_not_only_its_elaboration(
        self,
    ) -> None:
        accepted = FindingMother.low_severity(path="src/y.py")
        body = PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=(),
            findings=(accepted,),
            deviations=(),
            subissue=46,
        ).rendered()

        assert f"- {accepted.severity}: {accepted.rule} - {accepted.detail} ({accepted.path})" in body

    def test_a_finding_the_judge_approved_without_correcting_is_marked_apart_from_the_debt_the_implementer_declared(
        self,
    ) -> None:
        accepted = FindingMother.low_severity(path="src/y.py")
        body = PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=("el cableado del subcomando queda para la slice-09",),
            findings=(accepted,),
            deviations=(),
            subissue=46,
        ).rendered()

        assert (
            "## Deuda aceptada\n"
            "- el cableado del subcomando queda para la slice-09\n"
            "\n"
            "Hallazgos que el juez dejo pasar sin corregir:\n"
            f"- {accepted.severity}: {accepted.rule} - {accepted.detail} ({accepted.path})\n"
            "\n"
            "Closes #46"
        ) in body

    def test_a_finding_the_judge_approved_without_correcting_opens_the_debt_section_even_with_nothing_left_out(
        self,
    ) -> None:
        accepted = FindingMother.low_severity()
        body = PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=(),
            findings=(accepted,),
            deviations=(),
            subissue=46,
        ).rendered()

        assert "## Deuda aceptada" in body

    @staticmethod
    def _with_deviations(deviations: tuple[str, ...], *, debt: tuple[str, ...] = ()) -> PullRequestBody:
        return PullRequestBody(
            intention=_INTENTION,
            criteria=_CRITERIA,
            debt=debt,
            findings=(),
            deviations=deviations,
            subissue=46,
        )

    def test_two_declared_deviations_fill_their_own_section_one_bullet_each(self) -> None:
        body = self._with_deviations(
            (
                "el puerto no admite la firma decidida porque ya la consume otro adaptador",
                "la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza",
            )
        ).rendered()

        assert (
            "## Decisiones de diseno no seguidas\n"
            "- el puerto no admite la firma decidida porque ya la consume otro adaptador\n"
            "- la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza\n"
            "\n"
            "Closes #46"
        ) in body

    def test_the_deviations_section_comes_after_the_accepted_debt_section(self) -> None:
        body = self._with_deviations(
            ("la excepcion hereda de OSError",), debt=("el cableado del subcomando queda para la slice-09",)
        ).rendered()

        assert body.index("## Deuda aceptada") < body.index("## Decisiones de diseno no seguidas")

    def test_a_slice_that_deviated_from_nothing_leaves_the_section_out_instead_of_writing_none(self) -> None:
        assert "## Decisiones de diseno no seguidas" not in self._with_deviations(()).rendered()
