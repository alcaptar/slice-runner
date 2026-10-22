from __future__ import annotations

from dataclasses import replace

from slice_runner.infrastructure.slice_pull_request import SlicePullRequest
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother


class TestSlicePullRequest:
    def test_the_title_is_a_conventional_commit_scoped_by_the_name_of_the_slice(self) -> None:
        title = SlicePullRequest().title(SubIssueMother.pending())

        assert title == "feat(prechecks-deterministas): comprobar antes de tocar codigo"

    def test_the_first_round_commit_message_opens_with_that_same_title_so_the_subject_line_stays_conventional(
        self,
    ) -> None:
        message = SlicePullRequest().commit_message(SubIssueMother.pending(), round=1)

        assert message.splitlines()[0] == SlicePullRequest().title(SubIssueMother.pending())

    def test_a_subissue_carrying_a_user_story_opens_the_pull_request_title_with_its_key(self) -> None:
        title = SlicePullRequest().title(SubIssueMother.carrying_a_user_story())

        assert title == "PROJ-1234-05 feat(prechecks-deterministas): comprobar antes de tocar codigo"

    def test_a_subissue_carrying_a_user_story_keeps_the_first_round_commit_subject_without_the_key(self) -> None:
        subissue = SubIssueMother.carrying_a_user_story()

        title = SlicePullRequest().title(subissue)
        commit_subject = SlicePullRequest().commit_message(subissue, round=1).splitlines()[0]

        assert commit_subject == "feat(prechecks-deterministas): comprobar antes de tocar codigo"
        assert title != commit_subject

    def test_a_correction_round_names_its_own_number_so_the_history_tells_it_apart_from_what_it_corrects(
        self,
    ) -> None:
        message = SlicePullRequest().commit_message(SubIssueMother.pending(), round=2)

        assert message.splitlines()[0] == "feat(prechecks-deterministas): comprobar antes de tocar codigo (vuelta 2)"

    def test_the_commit_message_credits_claude_as_co_author_because_a_harness_wrote_the_code(self) -> None:
        message = SlicePullRequest().commit_message(SubIssueMother.pending(), round=1)

        assert message.endswith("Co-Authored-By: Claude <noreply@anthropic.com>")
        assert message.splitlines()[1] == ""

    def test_the_body_carries_the_intention_a_confirmation_of_the_criteria(
        self,
    ) -> None:
        body = SlicePullRequest().body(SubIssueMother.pending(), debt=(), findings=(), deviations=())

        assert body == (
            "## Intencion\n"
            "hoy nada evita reimplementar una slice ya entregada\n"
            "\n"
            "## Criterios de aceptacion cumplidos\n"
            "- los 2 criterios de aceptacion de la subissue #45 quedan cumplidos, su detalle vive en el issue\n"
            "\n"
            "Closes #45"
        )

    def test_a_signal_the_subissue_declared_never_reaches_the_body_because_nothing_checks_it_after_the_deploy(
        self,
    ) -> None:
        body = SlicePullRequest().body(
            replace(SubIssueMother.pending(), signal="tasa de error 5xx de api-web en produccion"),
            debt=(),
            findings=(),
            deviations=(),
        )

        assert "## Senal a comprobar tras el despliegue" not in body
        assert "tasa de error 5xx de api-web en produccion" not in body

    def test_the_criteria_the_subissue_declared_are_not_reproduced_word_for_word_in_the_body(self) -> None:
        subissue = SubIssueMother.pending()

        body = SlicePullRequest().body(subissue, debt=(), findings=(), deviations=())

        for criterion in subissue.criteria:
            assert criterion not in body

    def test_a_subissue_with_one_criterion_is_confirmed_in_the_singular_and_not_as_los_1_criterios(self) -> None:
        body = SlicePullRequest().body(SubIssueMother.with_a_single_criterion(), debt=(), findings=(), deviations=())

        assert (
            "## Criterios de aceptacion cumplidos\n"
            "- el criterio de aceptacion de la subissue #45 queda cumplido, su detalle vive en el issue\n"
        ) in body

    def test_a_slice_that_declared_no_intention_says_so_in_the_heading_instead_of_presenting_it_as_declared(
        self,
    ) -> None:
        body = SlicePullRequest().body(
            SubIssueMother.without_a_declared_intention(), debt=(), findings=(), deviations=()
        )

        assert body.startswith("## Intencion (inferida del issue, no declarada)\n")

    def test_the_debt_the_implementer_declared_fills_the_debt_section(self) -> None:
        body = SlicePullRequest().body(
            SubIssueMother.pending(),
            debt=("el cableado del subcomando queda para otra slice",),
            findings=(),
            deviations=(),
        )

        assert ("## Deuda aceptada\n- el cableado del subcomando queda para otra slice\n\nCloses #45") in body

    def test_a_slice_with_nothing_left_out_writes_no_debt_section(self) -> None:
        body = SlicePullRequest().body(SubIssueMother.pending(), debt=(), findings=(), deviations=())

        assert "## Deuda aceptada" not in body

    def test_a_finding_the_judge_approved_without_correcting_reaches_the_debt_section_too(self) -> None:
        accepted = FindingMother.low_severity()

        body = SlicePullRequest().body(SubIssueMother.pending(), debt=(), findings=(accepted,), deviations=())

        assert (
            "## Deuda aceptada\n"
            "Hallazgos que el juez dejo pasar sin corregir:\n"
            f"- {accepted.severity}: {accepted.rule} - {accepted.detail} ({accepted.path})\n"
        ) in body

    def test_the_deviations_the_implementer_declared_fill_the_deviations_section(self) -> None:
        body = SlicePullRequest().body(
            SubIssueMother.pending(),
            debt=(),
            findings=(),
            deviations=("el puerto no admite la firma decidida porque ya la consume otro adaptador",),
        )

        assert (
            "## Decisiones de diseno no seguidas\n"
            "- el puerto no admite la firma decidida porque ya la consume otro adaptador\n"
            "\n"
            "Closes #45"
        ) in body
