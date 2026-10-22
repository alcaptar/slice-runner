from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.severity import Severity


@dataclass(frozen=True, kw_only=True, slots=True)
class Finding:
    rule: str
    path: str
    severity: Severity
    evidence: str
    detail: str
    line: int | None = None
