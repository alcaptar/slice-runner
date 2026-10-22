from __future__ import annotations

from abc import ABC, abstractmethod


class ProgramVersion(ABC):
    @abstractmethod
    def read(self) -> str: ...
