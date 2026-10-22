from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.closed_as import ClosedAs

if TYPE_CHECKING:
    from slice_runner.domain.slice_status import SliceStatus


@dataclass(frozen=True, kw_only=True, slots=True)
class FeatureStatusReport:
    MINIMUM_IDENTIFIER_WIDTH: ClassVar[int] = 10

    statuses: tuple[SliceStatus, ...]

    def rendered(self) -> str:
        longest = max((len(status.sub_issue.slice_id.canonical) for status in self.statuses), default=0)
        identifier_width = max(longest, self.MINIMUM_IDENTIFIER_WIDTH)

        return "\n".join(self._line(status, identifier_width) for status in self.statuses)

    def _line(self, status: SliceStatus, identifier_width: int) -> str:
        parts = [f"{status.sub_issue.slice_id.canonical:<{identifier_width}}", f"{self._label(status):<28}"]
        run = status.sub_issue.run
        if run is not None:
            parts.append(run.step.value)
            if status.shown_cost_usd is not None:
                parts.append(f"${status.shown_cost_usd:.2f}")
            if run.implement_retries > 0:
                parts.append(f"retries={run.implement_retries}")
        elif status.record is not None:
            parts.append(ClosedAs.of(status.record.closure).value)
            if status.shown_cost_usd is not None:
                parts.append(f"${status.shown_cost_usd:.2f}")
        if status.pull_request is not None:
            parts.append(f"#{status.pull_request}")

        return " ".join(parts)

    @staticmethod
    def _label(status: SliceStatus) -> str:
        if status.sub_issue.label is not None:
            return status.sub_issue.label.value

        return status.sub_issue.state.value
