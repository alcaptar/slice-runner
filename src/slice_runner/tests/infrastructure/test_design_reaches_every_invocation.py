from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.design import Design

_READER = RecordedSourceReader()


class TestTheImplementerReceivesTheDesignsOfItsSlice:
    @staticmethod
    def _text(assignment: Assignment) -> str:
        return " ".join(ImplementerInvocation(assignment=assignment, reader=_READER).text.split())

    def test_the_html_of_the_design_the_slice_cites_travels_in_the_prompt(self) -> None:
        text = ImplementerInvocation(
            assignment=AssignmentMother.of_a_slice_with_the_board_design(), reader=_READER
        ).text

        assert DesignMother.BOARD_HTML in text

    def test_two_designs_travel_both_and_not_only_the_first(self) -> None:
        text = ImplementerInvocation(assignment=AssignmentMother.of_a_slice_with_two_designs(), reader=_READER).text

        assert DesignMother.BOARD_HTML in text
        assert DesignMother.DETAIL_HTML in text

    def test_the_design_is_its_own_section_apart_from_the_conventions_of_the_repo(self) -> None:
        text = ImplementerInvocation(
            assignment=AssignmentMother.of_a_slice_with_the_board_design(), reader=_READER
        ).text

        assert text.index("\n## Diseno\n") > text.index("- fuentes de convencion")
        assert text.index(DesignMother.BOARD_HTML) > text.index("\n## Diseno\n")

    def test_a_slice_that_cites_no_design_carries_no_html_section(self) -> None:
        text = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=_READER).text

        assert "## Diseno" not in text

    def test_with_a_design_the_brief_asks_to_copy_the_fixed_texts_literally(self) -> None:
        said = self._text(AssignmentMother.of_a_slice_with_the_board_design())

        assert "Copia literalmente los textos fijos del diseno" in said

    def test_with_a_design_the_brief_asks_to_use_only_colours_of_the_palette_of_the_repo(self) -> None:
        said = self._text(AssignmentMother.of_a_slice_with_the_board_design())

        assert "usa solo colores de la paleta del repo" in said

    def test_without_a_design_the_brief_mentions_neither_the_copy_nor_the_palette(self) -> None:
        said = self._text(AssignmentMother.of_the_first_round())

        assert "paleta" not in said
        assert "Copia literalmente" not in said

    def test_the_design_brief_comes_after_the_data_of_the_slice(self) -> None:
        text = ImplementerInvocation(
            assignment=AssignmentMother.of_a_slice_with_the_board_design(), reader=_READER
        ).text

        assert text.index("</datos_de_la_slice id=") < text.index("\n## Encargo de diseno\n")


class TestTheJudgeReceivesTheDesignsOfTheSliceItJudges:
    @staticmethod
    def _judged(*, designs: tuple[Design, ...]) -> str:
        review = SliceUnderReviewMother.of_the_slice(designs=designs)

        return JudgeInvocation(judge=JudgeMother.adversarial(), review=review, reader=_READER).text

    def test_the_html_of_the_design_the_slice_cites_travels_in_the_prompt(self) -> None:
        assert DesignMother.BOARD_HTML in self._judged(designs=(DesignMother.board(),))

    def test_two_designs_travel_both_and_not_only_the_first(self) -> None:
        text = self._judged(designs=(DesignMother.board(), DesignMother.detail()))

        assert DesignMother.BOARD_HTML in text
        assert DesignMother.DETAIL_HTML in text

    def test_a_slice_that_cites_no_design_carries_no_html_section(self) -> None:
        assert "## Diseno" not in self._judged(designs=())

    @pytest.mark.parametrize(
        "asked",
        [
            "senalar como hallazgo un color que el diff usa fuera de la paleta del repo",
            "senalar como hallazgo un texto fijo del diseno que el diff cambia",
            "No senales datos dinamicos ni mensajes nuevos",
        ],
    )
    def test_with_a_design_the_rubric_asks_to_flag_what_leaves_the_design_and_only_that(self, asked: str) -> None:
        assert asked in " ".join(self._judged(designs=(DesignMother.board(),)).split())

    def test_without_a_design_the_rubric_does_not_mention_the_palette(self) -> None:
        assert "paleta" not in self._judged(designs=())

    def test_the_design_rubric_closes_the_prompt_after_the_diff_when_a_design_travels(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(designs=(DesignMother.board(),), text="+x = 1\n")

        text = JudgeInvocation(judge=JudgeMother.adversarial(), review=review, reader=_READER).text

        assert text.index("</diff") < text.index(SliceVerifierJudge.DESIGN_RUBRIC)
        assert text.endswith(SliceVerifierJudge.DESIGN_RUBRIC)
