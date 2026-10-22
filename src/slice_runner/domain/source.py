from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    DOC = "doc"
    SKILL = "skill"


@dataclass(frozen=True, kw_only=True, slots=True)
class Source:
    kind: SourceKind
    path: str
