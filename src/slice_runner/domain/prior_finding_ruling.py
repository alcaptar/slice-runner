from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PriorFindingState(StrEnum):
    FIXED = "corregido"
    STILL_STANDING = "sigue"
    RETIRED = "retirado"


@dataclass(frozen=True, kw_only=True, slots=True)
class PriorFindingRuling:
    id: str
    state: PriorFindingState
    reason: str = ""
