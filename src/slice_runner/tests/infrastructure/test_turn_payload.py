from __future__ import annotations

from slice_runner.infrastructure.turn_payload import TurnPayload
from slice_runner.tests.mothers.turn_mother import TurnMother


class TestWhatTheProgramEmits:
    def test_the_turn_serialises_with_the_slice_the_step_the_number_the_tool_and_its_target(self) -> None:
        assert TurnPayload.from_domain(TurnMother.first()).to_contract() == {
            "slice_id": "slice-05",
            "step": "implement",
            "number": 1,
            "tool": "Write",
            "target": "hello.py",
        }

    def test_a_turn_without_a_target_leaves_it_out_instead_of_emitting_null(self) -> None:
        assert TurnPayload.from_domain(TurnMother.without_a_target()).to_contract() == {
            "slice_id": "slice-05",
            "step": "implement",
            "number": 3,
            "tool": "StructuredOutput",
        }
