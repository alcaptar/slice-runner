from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.check_verdict import CheckVerdict

if TYPE_CHECKING:
    from slice_runner.domain.readiness_check import ReadinessCheck


@dataclass(frozen=True, kw_only=True, slots=True)
class Readiness:
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return not any(check.verdict is CheckVerdict.MISSING for check in self.checks)
