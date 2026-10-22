from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.conversation_spend import ConversationSpend


@dataclass(frozen=True, kw_only=True, slots=True)
class ToolCall:
    name: str
    summary: str
    result: str | None
    path: str | None
    command: str | None
    failed: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class ConversationTurn:
    number: int
    text: str
    tool_calls: tuple[ToolCall, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class Conversation:
    turns: tuple[ConversationTurn, ...]
    spend: ConversationSpend
