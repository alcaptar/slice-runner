from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def sleep(self, *, seconds: int) -> None: ...

    @abstractmethod
    def now(self) -> datetime: ...
