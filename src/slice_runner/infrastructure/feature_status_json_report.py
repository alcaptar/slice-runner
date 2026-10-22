from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.infrastructure.slice_status_line_payload import SliceStatusLinePayload

if TYPE_CHECKING:
    from slice_runner.domain.slice_status import SliceStatus


class FeatureStatusJsonReport:
    def __init__(self, *, statuses: tuple[SliceStatus, ...]) -> None:
        self._statuses = statuses

    def lines(self) -> tuple[str, ...]:
        return tuple(
            json.dumps(SliceStatusLinePayload.from_domain(status).to_contract(), ensure_ascii=False)
            for status in self._statuses
        )
