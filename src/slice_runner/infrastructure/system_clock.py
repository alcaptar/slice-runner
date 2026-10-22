from __future__ import annotations

import time
from datetime import UTC, datetime

from slice_runner.domain.clock import Clock


class SystemClock(Clock):
    def sleep(self, *, seconds: int) -> None:
        time.sleep(seconds)

    def now(self) -> datetime:
        return datetime.now(UTC)
