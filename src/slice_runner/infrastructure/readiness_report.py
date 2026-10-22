from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.readiness import Readiness
    from slice_runner.domain.readiness_check import ReadinessCheck


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadinessReport:
    readiness: Readiness

    def rendered(self) -> str:
        return "\n".join(self._lines)

    @property
    def _lines(self) -> list[str]:
        lines: list[str] = []
        for check in self.readiness.checks:
            lines.append(self._line(check))
            if check.fix is not None:
                lines.append(f"        {check.fix}")

        return lines

    @staticmethod
    def _line(check: ReadinessCheck) -> str:
        return f"{check.verdict.value:<7} {check.name:<20} {check.detail}"
