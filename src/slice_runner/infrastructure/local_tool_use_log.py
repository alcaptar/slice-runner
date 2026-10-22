from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.tool_use_log import ToolUseLog
from slice_runner.infrastructure.tool_use_payload import CallToolUsePayload, UnrecordedCallToolUsePayload

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, UnrecordedCallToolUse


class LocalToolUseLog(ToolUseLog):
    LEDGER: ClassVar[str] = "tool-uses"
    UNRECORDED_LEDGER: ClassVar[str] = "unrecorded-tool-uses"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._uses: DurableLedger[CallToolUsePayload] = DurableLedger(name=self.LEDGER, row=CallToolUsePayload)
        self._unrecorded: DurableLedger[UnrecordedCallToolUsePayload] = DurableLedger(
            name=self.UNRECORDED_LEDGER, row=UnrecordedCallToolUsePayload
        )

    def record(self, call: HarnessCallToolUse) -> None:
        self._uses.append(CallToolUsePayload.from_call(call, ts=self._clock.now().isoformat()))

    def record_unrecorded(self, call: UnrecordedCallToolUse) -> None:
        self._unrecorded.append(UnrecordedCallToolUsePayload.from_call(call, ts=self._clock.now().isoformat()))
