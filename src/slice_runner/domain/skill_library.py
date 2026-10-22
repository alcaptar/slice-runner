from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class SkillLibrary(ABC):
    @abstractmethod
    def root(self) -> Path: ...

    @abstractmethod
    def directories(self) -> tuple[Path, ...]: ...

    @abstractmethod
    def installed(self, name: str) -> Path | None: ...
