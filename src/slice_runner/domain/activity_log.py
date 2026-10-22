from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.activity import Activity
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class ActivityLog(ABC):
    @abstractmethod
    def restart(self, coordinates: SliceCoordinates) -> None: ...

    @abstractmethod
    def record(self, activity: Activity) -> None: ...
