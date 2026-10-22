from __future__ import annotations

import json

from slice_runner.domain.activity_actor import ActivityActor
from slice_runner.domain.step import Step
from slice_runner.infrastructure.harness_turn_watch import HarnessTurnWatch
from slice_runner.tests.doubles import RecordedActivityLog, RecordedTurnLog
from slice_runner.tests.mothers.harness_call_spend_mother import HarnessCallSpendMother


class Watching:
    @staticmethod
    def _watch(turns: RecordedTurnLog) -> HarnessTurnWatch:
        return HarnessTurnWatch(
            turns=turns,
            activity=RecordedActivityLog(),
            coordinates=HarnessCallSpendMother.coordinates(),
            actor=ActivityActor.IMPLEMENTER,
            step=Step.IMPLEMENT,
        )


class TestTheTargetOfATool(Watching):
    def test_the_target_is_read_from_the_first_target_key_present_on_the_input(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "x", "name": "Write", "input": {"file_path": "/repo/hello.py"}}
                        ]
                    },
                }
            )
        )

        assert [(turn.tool, turn.target) for turn in turns.turns] == [("Write", "/repo/hello.py")]

    def test_a_tool_use_with_none_of_the_target_keys_is_observed_with_no_target(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": "x", "name": "StructuredOutput", "input": {}}]},
                }
            )
        )

        assert turns.turns[0].target is None

    def test_several_tool_uses_of_the_same_turn_are_numbered_in_order(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "/repo/a.py"}},
                            {"type": "tool_use", "id": "b", "name": "Write", "input": {"file_path": "/repo/b.py"}},
                        ]
                    },
                }
            )
        )

        assert [turn.number for turn in turns.turns] == [1, 2]


class TestWhatIsSkippedInsteadOfObserved(Watching):
    def test_thinking_and_text_blocks_name_no_tool_so_they_are_not_observed(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "hi"}]},
                }
            )
        )

        assert turns.turns == []

    def test_a_line_that_is_not_an_assistant_turn_is_not_observed(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(json.dumps({"type": "system", "subtype": "init"}))

        assert turns.turns == []

    def test_a_line_that_is_not_json_at_all_is_skipped_instead_of_raising(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch("not json")

        assert turns.turns == []

    def test_content_that_is_not_a_list_is_skipped(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(json.dumps({"type": "assistant", "message": {"content": "not-a-list"}}))

        assert turns.turns == []

    def test_a_tool_use_block_whose_shape_this_program_cannot_read_is_skipped_instead_of_aborting(self) -> None:
        turns = RecordedTurnLog()
        watch = self._watch(turns)

        watch(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": "x", "name": "Write", "input": "not-a-dict"}]},
                }
            )
        )

        assert turns.turns == []
