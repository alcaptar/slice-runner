from __future__ import annotations

from slice_runner.domain.conversation import Conversation, ConversationTurn, ToolCall
from slice_runner.domain.conversation_spend import ConversationSpend


class ConversationMother:
    @staticmethod
    def with_a_decision_and_a_tool_call() -> Conversation:
        return Conversation(
            turns=(
                ConversationTurn(number=1, text="Now let's confirm RED before implementing:", tool_calls=()),
                ConversationTurn(
                    number=2,
                    text="",
                    tool_calls=(
                        ToolCall(
                            name="Bash",
                            summary='{"command": "uv run pytest -x"}',
                            result="1 failed, 0 passed",
                            path=None,
                            command="uv run pytest -x",
                        ),
                    ),
                ),
            ),
            spend=ConversationSpend(
                input_tokens=4, output_tokens=450, cache_creation_tokens=3752, cache_read_tokens=418026
            ),
        )

    @staticmethod
    def with_a_turn_that_left_nothing_to_show() -> Conversation:
        return Conversation(
            turns=(ConversationTurn(number=1, text="", tool_calls=()),),
            spend=ConversationSpend(),
        )
