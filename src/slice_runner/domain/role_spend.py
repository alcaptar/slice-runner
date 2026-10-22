from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class RoleSpend:
    step: Step
    spend: HarnessSpend
