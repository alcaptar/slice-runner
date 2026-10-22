from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.conversation_spend import ConversationSpend
from slice_runner.domain.exceptions import UnreadableConversationError
from slice_runner.infrastructure.contract_model import ContractModel


class TranscriptUsage(ContractModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = Field(alias="cache_creation_input_tokens", default=0)
    cache_read_tokens: int = Field(alias="cache_read_input_tokens", default=0)

    def to_domain(self) -> ConversationSpend:
        return ConversationSpend(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(
                input_tokens=data.get("input_tokens"),
                output_tokens=data.get("output_tokens"),
                cache_creation_input_tokens=data.get("cache_creation_input_tokens"),
                cache_read_input_tokens=data.get("cache_read_input_tokens"),
            ),
            "a message usage block is not one this program can read",
            UnreadableConversationError,
        )


class TranscriptTextBlock(ContractModel):
    text: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(text=data.get("text")),
            "a text content block is not one this program can read",
            UnreadableConversationError,
        )


class TranscriptToolUseBlock(ContractModel):
    id: str = ""
    name: str = ""
    input: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(id=data.get("id"), name=data.get("name"), input=data.get("input")),
            "a tool_use content block is not one this program can read",
            UnreadableConversationError,
        )


class TranscriptToolResultBlock(ContractModel):
    tool_use_id: str = ""
    content: object = None
    is_error: bool = Field(default=False, strict=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(
                tool_use_id=data.get("tool_use_id"), content=data.get("content"), is_error=data.get("is_error")
            ),
            "a tool_result content block is not one this program can read",
            UnreadableConversationError,
        )


class TranscriptMessage(ContractModel):
    id: str = ""
    usage: dict[str, object] | None = None
    content: tuple[dict[str, object], ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        content = data.get("content")
        return cls._validated(
            cls._present(
                id=data.get("id"),
                usage=data.get("usage"),
                content=[block for block in content if isinstance(block, dict)] if isinstance(content, list) else None,
            ),
            "a message envelope is not one this program can read",
            UnreadableConversationError,
        )
