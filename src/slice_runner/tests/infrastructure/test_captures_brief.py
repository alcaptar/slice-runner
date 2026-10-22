from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.assignment_mother import AssignmentMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment

_READER = RecordedSourceReader()


class TestTheImplementerIsAskedForTheCapturesOfItsDesign:
    @staticmethod
    def _said(assignment: Assignment) -> str:
        return " ".join(ImplementerInvocation(assignment=assignment, reader=_READER).text.split())

    @classmethod
    def _with_design(cls) -> str:
        return cls._said(AssignmentMother.of_a_slice_with_the_board_design())

    def test_it_is_told_the_absolute_path_of_the_captures_directory_of_its_worktree(self) -> None:
        assignment = AssignmentMother.of_a_slice_with_the_board_design()

        assert f"{assignment.worktree}/.design-captures" in self._said(assignment)

    def test_it_is_told_the_manifest_goes_in_that_directory_with_the_shape_of_the_contract(self) -> None:
        said = self._with_design()

        assert "/.design-captures/manifest.json" in said
        assert '{"captures": [{"design": "<nombre del diseno>", "state": "<estado que muestra>", "file":' in said

    def test_capturing_is_the_last_step_of_the_round(self) -> None:
        assert "ultimo paso de la vuelta" in self._with_design()

    def test_it_is_told_to_capture_as_the_conventions_of_the_repo_say(self) -> None:
        assert "Captura como digan las fuentes de convencion del repo" in self._with_design()

    def test_when_it_cannot_capture_it_is_told_to_write_missing_with_its_reason(self) -> None:
        assert '{"missing": "<motivo>"}' in self._with_design()

    def test_it_is_told_never_to_declare_a_file_of_that_directory_among_the_ones_it_touches(self) -> None:
        assert "Nunca declares ningun fichero de ese directorio" in self._with_design()

    def test_the_captures_brief_comes_after_the_data_of_the_slice(self) -> None:
        text = ImplementerInvocation(
            assignment=AssignmentMother.of_a_slice_with_the_board_design(), reader=_READER
        ).text

        assert text.index("</datos_de_la_slice id=") < text.index("\n## Encargo de capturas\n")

    def test_a_slice_that_cites_no_design_is_asked_for_no_captures(self) -> None:
        said = self._said(AssignmentMother.of_the_first_round())

        assert "capturas" not in said
        assert ".design-captures" not in said
