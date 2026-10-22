from __future__ import annotations

from slice_runner.domain.step import Step
from slice_runner.infrastructure.conversation_report import ConversationReport
from slice_runner.tests.mothers.conversation_mother import ConversationMother

_SLICE = "slice-05"
_SESSION = "779e530f-c285-495c-bbdc-f2896f81fe25"


class TestTheHeaderOfTheReport:
    def test_the_slice_the_step_and_the_session_are_named_so_the_reader_knows_what_they_are_looking_at(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_decision_and_a_tool_call(),
        ).rendered()

        assert f"{_SLICE} - {Step.IMPLEMENT} - session {_SESSION}" in rendered

    def test_the_turn_count_is_the_number_of_turns_even_the_ones_that_render_nothing(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_decision_and_a_tool_call(),
        ).rendered()

        assert "2 turns" in rendered

    def test_the_spend_of_the_conversation_is_reported_as_tokens(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_decision_and_a_tool_call(),
        ).rendered()

        assert "4 in" in rendered
        assert "450 out" in rendered
        assert "3752 cache-write" in rendered
        assert "418026 cache-read" in rendered


class TestTheTurnsOfTheReport:
    def test_the_text_of_a_turn_appears_under_its_number(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_decision_and_a_tool_call(),
        ).rendered()

        assert "[1]\nNow let's confirm RED before implementing:" in rendered

    def test_a_tool_call_names_the_tool_its_input_and_what_it_read_back(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_decision_and_a_tool_call(),
        ).rendered()

        assert 'tool: Bash({"command": "uv run pytest -x"})' in rendered
        assert "-> 1 failed, 0 passed" in rendered

    def test_a_turn_that_left_nothing_to_show_is_skipped_instead_of_printing_an_empty_entry(self) -> None:
        rendered = ConversationReport(
            slice_id=_SLICE,
            step=Step.IMPLEMENT,
            session=_SESSION,
            conversation=ConversationMother.with_a_turn_that_left_nothing_to_show(),
        ).rendered()

        assert "[1]" not in rendered
        assert "1 turns" in rendered
