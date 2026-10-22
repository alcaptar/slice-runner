from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.check_verdict import CheckVerdict


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadinessCheck:
    name: str
    verdict: CheckVerdict
    detail: str
    fix: str | None = None
