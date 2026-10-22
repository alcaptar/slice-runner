from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

if TYPE_CHECKING:
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures

_READER = RecordedSourceReader()


class TestTheJudgeReceivesTheCapturesOfTheDesigns:
    @staticmethod
    def _judged(captures: DesignCaptures | MissingDesignCaptures, *, cites_a_design: bool = True) -> str:
        designs = (DesignMother.board(), DesignMother.detail()) if cites_a_design else ()
        review = SliceUnderReviewMother.of_the_slice(designs=designs, captures=captures)

        return " ".join(JudgeInvocation(judge=JudgeMother.adversarial(), review=review, reader=_READER).text.split())

    def test_two_captures_travel_with_both_absolute_paths(self) -> None:
        text = self._judged(DesignCapturesMother.of_the_board_and_the_detail())

        assert DesignCapturesMother.BOARD_PATH in text
        assert DesignCapturesMother.DETAIL_PATH in text

    def test_each_path_travels_with_the_design_and_the_state_it_captures(self) -> None:
        text = self._judged(DesignCapturesMother.of_the_board_and_the_detail())

        assert f"tablero | 80 columns, two slices running: {DesignCapturesMother.BOARD_PATH}" in text
        assert f"detalle | one slice with a finding: {DesignCapturesMother.DETAIL_PATH}" in text

    def test_the_prompt_says_a_capture_is_support_and_not_enough_to_approve(self) -> None:
        text = self._judged(DesignCapturesMother.of_the_board_and_the_detail())

        assert "Una captura es apoyo y no basta para aprobar" in text

    def test_missing_captures_are_announced_with_their_reason_and_no_path(self) -> None:
        text = self._judged(DesignCapturesMother.missing())

        assert f"No hay capturas: {DesignCapturesMother.REASON}" in text
        assert ".design-captures" not in text

    def test_a_slice_that_cites_no_design_carries_no_captures_section(self) -> None:
        text = self._judged(DesignCapturesMother.none(), cites_a_design=False)

        assert "## Capturas del diseno" not in text
        assert "No hay capturas" not in text

    def test_the_captures_section_comes_after_the_design_and_before_the_diff(self) -> None:
        text = self._judged(DesignCapturesMother.of_the_board_and_the_detail())

        assert text.index("## Diseno") < text.index("## Capturas del diseno") < text.index("<diff")
