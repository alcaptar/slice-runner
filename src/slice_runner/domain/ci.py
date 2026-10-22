from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.ci_status import CiStatus


class Ci(ABC):
    @abstractmethod
    def status(self, *, repo: str, pull_request: int) -> CiStatus: ...
