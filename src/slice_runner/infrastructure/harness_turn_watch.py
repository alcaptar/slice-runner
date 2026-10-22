from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.activity import Activity
from slice_runner.domain.exceptions import UnreadableConversationError
from slice_runner.infrastructure.conversation_transcript import TranscriptToolUseBlock
from slice_runner.infrastructure.turn_log import HarnessTurn

if TYPE_CHECKING:
    from slice_runner.domain.activity_actor import ActivityActor
    from slice_runner.domain.activity_log import ActivityLog
    from slice_runner.domain.slice_coordinates import SliceCoordinates
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.turn_log import TurnLog


class HarnessTurnWatch:
    _TARGET_KEYS: ClassVar[tuple[str, ...]] = ("file_path", "path", "pattern", "command")

    def __init__(
        self,
        *,
        turns: TurnLog,
        activity: ActivityLog,
        coordinates: SliceCoordinates,
        actor: ActivityActor,
        step: Step,
    ) -> None:
        self._turns = turns
        self._activity = activity
        self._coordinates = coordinates
        self._actor = actor
        self._step = step
        self._seen = 0

    def __call__(self, line: str) -> None:
        for tool_use in self._tool_uses_of(line):
            self._seen += 1
            target = self._target_of(tool_use.input)
            self._turns.observe(
                HarnessTurn(
                    slice_id=self._coordinates.slice_id.text,
                    step=self._step,
                    number=self._seen,
                    tool=tool_use.name,
                    target=target,
                )
            )
            self._activity.record(
                Activity(
                    coordinates=self._coordinates,
                    actor=self._actor,
                    tool=tool_use.name,
                    target=target or "",
                )
            )

    @classmethod
    def _tool_uses_of(cls, line: str) -> tuple[TranscriptToolUseBlock, ...]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return ()

        if not isinstance(data, dict) or data.get("type") != "assistant":
            return ()

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return ()

        blocks = (block for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
        return tuple(tool_use for tool_use in (cls._legible(block) for block in blocks) if tool_use is not None)

    @staticmethod
    def _legible(block: dict[str, object]) -> TranscriptToolUseBlock | None:
        try:
            return TranscriptToolUseBlock.from_dict(block)
        except UnreadableConversationError:
            return None

    @classmethod
    def _target_of(cls, tool_input: dict[str, object]) -> str | None:
        for key in cls._TARGET_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str):
                return value

        return None
