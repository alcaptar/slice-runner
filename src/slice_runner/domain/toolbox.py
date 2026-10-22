from __future__ import annotations

from abc import ABC, abstractmethod


class Toolbox(ABC):
    @abstractmethod
    def version_of(self, executable: str) -> str | None: ...
