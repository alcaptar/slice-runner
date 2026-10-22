from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.closed_slice_scope import ClosedSliceScope
    from slice_runner.domain.metrics_log import MetricsLog


@dataclass(frozen=True, kw_only=True, slots=True)
class ListClosedSlicesParams:
    scope: ClosedSliceScope


class ListClosedSlices:
    def __init__(self, *, metrics_log: MetricsLog) -> None:
        self._metrics_log = metrics_log

    def execute(self, params: ListClosedSlicesParams) -> tuple[ClosedSliceRecord, ...]:
        return self._metrics_log.closed_slices(params.scope)
