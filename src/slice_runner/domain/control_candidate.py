from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ControlCandidateSource(StrEnum):
    MAKEFILE = "makefile"
    PYPROJECT = "pyproject"
    TOX = "tox"


@dataclass(frozen=True, kw_only=True, slots=True)
class ControlCandidate:
    name: str
    command: str
    source: ControlCandidateSource
    hint: str = ""
