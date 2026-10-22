from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, kw_only=True, slots=True)
class Judge:
    rubric: str
    tools: tuple[str, ...]
    readable: tuple[Path, ...] = ()

    def also_reading(self, *directories: Path) -> Judge:
        return replace(self, readable=(*self.readable, *directories))
