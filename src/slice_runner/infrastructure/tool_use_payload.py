from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.step import Step
from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, ToolUse, UnrecordedCallToolUse


class ToolUsePayload(ContractModel):
    turn: int
    tool: str
    path: str | None = None
    command: str | None = None
    failed: bool | None = None

    @classmethod
    def from_domain(cls, use: ToolUse) -> Self:
        return cls(turn=use.turn, tool=use.tool, path=use.path, command=use.command, failed=use.failed or None)


class CallToolUsePayload(StampedRow):
    step: Step
    session: str
    uses: tuple[ToolUsePayload, ...]

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_call(cls, call: HarnessCallToolUse, *, ts: str) -> Self:
        return cls._stamped(
            call.coordinates,
            ts=ts,
            step=call.step,
            session=call.session,
            uses=tuple(ToolUsePayload.from_domain(use) for use in call.uses),
        )


class UnrecordedCallToolUsePayload(StampedRow):
    step: Step
    session: str
    cause: UnrecordedConversationCause

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_call(cls, call: UnrecordedCallToolUse, *, ts: str) -> Self:
        return cls._stamped(call.coordinates, ts=ts, step=call.step, session=call.session, cause=call.cause)
