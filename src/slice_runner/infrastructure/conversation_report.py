from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.conversation import Conversation, ConversationTurn, ToolCall
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class ConversationReport:
    slice_id: str
    step: Step
    session: str
    conversation: Conversation

    def rendered(self) -> str:
        return "\n".join([self._header, "", *self._turns])

    @property
    def _header(self) -> str:
        spend = self.conversation.spend

        return (
            f"{self.slice_id} - {self.step} - session {self.session} "
            f"({len(self.conversation.turns)} turns, "
            f"{spend.input_tokens} in + {spend.output_tokens} out + "
            f"{spend.cache_creation_tokens} cache-write + {spend.cache_read_tokens} cache-read tokens)"
        )

    @property
    def _turns(self) -> list[str]:
        return [rendered for turn in self.conversation.turns if (rendered := self._turn(turn)) is not None]

    @classmethod
    def _turn(cls, turn: ConversationTurn) -> str | None:
        if not turn.text and not turn.tool_calls:
            return None

        lines = [f"[{turn.number}]"]
        if turn.text:
            lines.append(turn.text)
        lines.extend(cls._tool_call(call) for call in turn.tool_calls)

        return "\n".join(lines)

    @staticmethod
    def _tool_call(call: ToolCall) -> str:
        lines = [f"  tool: {call.name}({call.summary})"]
        if call.result:
            lines.append(f"  -> {call.result}")

        return "\n".join(lines)
