from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.activity import Activity


@dataclass(frozen=True, kw_only=True, slots=True)
class ObservedActivity:
    at: datetime
    activity: Activity
