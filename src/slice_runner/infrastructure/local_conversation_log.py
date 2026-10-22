from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.conversation import Conversation, ConversationTurn, ToolCall
from slice_runner.domain.conversation_log import ConversationLog
from slice_runner.domain.conversation_spend import ConversationSpend
from slice_runner.domain.exceptions import ConversationNotFoundError, UnreadableConversationError
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.conversation_transcript import (
    TranscriptMessage,
    TranscriptTextBlock,
    TranscriptToolResultBlock,
    TranscriptToolUseBlock,
    TranscriptUsage,
)

if TYPE_CHECKING:
    from pathlib import Path


class LocalConversationLog(ConversationLog):
    RESULT_EXCERPT_LENGTH: ClassVar[int] = 500
    OUTSIDE_A_PROJECT_DIRECTORY_NAME: ClassVar[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9-]")

    def read(self, *, session: str, worktree: str) -> Conversation:
        path = self._path(session=session, worktree=worktree)
        if not path.exists():
            raise ConversationNotFoundError(
                f"no conversation was ever recorded for session {session} under worktree {worktree}"
            )

        lines = self._decoded_lines(path)
        results = self._tool_results_of(lines)

        return Conversation(
            turns=tuple(self._turn_of(number, line, results) for number, line in enumerate(self._turns_of(lines), 1)),
            spend=self._spend_of(lines),
        )

    def _path(self, *, session: str, worktree: str) -> Path:
        encoded = self.OUTSIDE_A_PROJECT_DIRECTORY_NAME.sub("-", os.path.abspath(worktree).rstrip("/"))

        return ClaudeConfig.root().joinpath("projects", encoded, f"{session}.jsonl")

    @staticmethod
    def _decoded_lines(path: Path) -> list[dict[str, object]]:
        decoded = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as error:
                raise UnreadableConversationError(
                    f"the conversation transcript has a line that is not JSON: {error}"
                ) from error
            if not isinstance(data, dict):
                raise UnreadableConversationError(
                    f"a conversation transcript line has to be an object, not {type(data).__name__}"
                )
            decoded.append(data)

        return decoded

    @staticmethod
    def _turns_of(lines: list[dict[str, object]]) -> list[dict[str, object]]:
        return [line for line in lines if line.get("type") == "assistant"]

    @classmethod
    def _tool_results_of(cls, lines: list[dict[str, object]]) -> dict[str, TranscriptToolResultBlock]:
        results: dict[str, TranscriptToolResultBlock] = {}
        for line in lines:
            if line.get("type") != "user":
                continue
            for block in cls._content_of(line):
                if block.get("type") != "tool_result":
                    continue
                result = TranscriptToolResultBlock.from_dict(block)
                if result.tool_use_id:
                    results[result.tool_use_id] = result

        return results

    @staticmethod
    def _content_of(line: dict[str, object]) -> tuple[dict[str, object], ...]:
        message = line.get("message")

        return TranscriptMessage.from_dict(message).content if isinstance(message, dict) else ()

    @classmethod
    def _excerpt(cls, content: object) -> str:
        return " ".join(cls._flattened(content).split())[: cls.RESULT_EXCERPT_LENGTH]

    @staticmethod
    def _flattened(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                TranscriptTextBlock.from_dict(block).text
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )

        return str(content)

    @classmethod
    def _turn_of(
        cls, number: int, line: dict[str, object], results: dict[str, TranscriptToolResultBlock]
    ) -> ConversationTurn:
        content = cls._content_of(line)
        text = " ".join(
            TranscriptTextBlock.from_dict(block).text for block in content if block.get("type") == "text"
        ).strip()
        tool_calls = tuple(cls._tool_call_of(block, results) for block in content if block.get("type") == "tool_use")

        return ConversationTurn(number=number, text=text, tool_calls=tool_calls)

    @classmethod
    def _tool_call_of(cls, block: dict[str, object], results: dict[str, TranscriptToolResultBlock]) -> ToolCall:
        tool_use = TranscriptToolUseBlock.from_dict(block)
        summary = json.dumps(tool_use.input, ensure_ascii=False)
        answered = results.get(tool_use.id) if tool_use.id else None

        return ToolCall(
            name=tool_use.name,
            summary=summary,
            result=cls._excerpt(answered.content) if answered is not None else None,
            path=cls._path_of(tool_use.input),
            command=cls._command_of(tool_use.input),
            failed=answered.is_error if answered is not None else False,
        )

    @staticmethod
    def _path_of(tool_input: dict[str, object]) -> str | None:
        for key in ("file_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value

        return None

    @staticmethod
    def _command_of(tool_input: dict[str, object]) -> str | None:
        value = tool_input.get("command")

        return value if isinstance(value, str) else None

    @classmethod
    def _spend_of(cls, lines: list[dict[str, object]]) -> ConversationSpend:
        seen: set[str] = set()
        spends = []
        for line in lines:
            raw_message = line.get("message")
            if not isinstance(raw_message, dict):
                continue
            message = TranscriptMessage.from_dict(raw_message)
            if not message.id or message.id in seen:
                continue
            seen.add(message.id)
            if message.usage is not None:
                spends.append(TranscriptUsage.from_dict(message.usage).to_domain())

        return ConversationSpend.summing(spends)
