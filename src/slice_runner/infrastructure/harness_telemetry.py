from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.activity_log import ActivityLog
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder
    from slice_runner.infrastructure.turn_log import TurnLog


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessTelemetry:
    trace: CallTrace
    turns: TurnLog
    activity: ActivityLog
    spend_log: CallSpendLog
    tool_uses: ToolUseRecorder
