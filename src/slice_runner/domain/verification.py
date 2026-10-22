from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.verdict import Verdict


@dataclass(frozen=True, kw_only=True, slots=True)
class Verification:
    verdict: Verdict
    spend: HarnessSpend
    session: str
    denied_reads: tuple[str, ...] = field(default=())
