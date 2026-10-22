from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.effort import Effort


@dataclass(frozen=True, kw_only=True, slots=True)
class RoleModels:
    implement: str
    verify: str
    implement_effort: Effort
    verify_effort: Effort
