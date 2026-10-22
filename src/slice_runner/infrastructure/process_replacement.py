from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NoReturn


class ExecutableNotFoundError(OSError):
    pass


class ProcessReplacement(ABC):
    @abstractmethod
    def replaced_by(self, argv: list[str]) -> NoReturn: ...
