from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.infrastructure.durable_ledger import ReadableDurableLedger
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.metrics_ledger_entry import MetricsLedgerEntry

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.closed_slice_scope import ClosedSliceScope


class LocalMetricsLog(MetricsLog):
    LEDGER: ClassVar[str] = "metrics"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._ledger: ReadableDurableLedger[MetricsEntryPayload] = ReadableDurableLedger(
            name=self.LEDGER, row=MetricsEntryPayload
        )

    def record(self, closed: ClosedSlice) -> None:
        payload = MetricsEntryPayload.from_domain(closed, ts=self._clock.now().isoformat())
        self._ledger.append(payload)

    def closed_slices(self, scope: ClosedSliceScope) -> tuple[ClosedSliceRecord, ...]:
        matching = self._ledger.rows_where(lambda data: MetricsEntryPayload.may_belong_to_the_scope(data, scope))
        records = (MetricsLedgerEntry.of(payload) for payload in matching)
        within_window = (record for record in records if scope.contains(record.ts))
        latest_by_identity: dict[tuple[str, int], ClosedSliceRecord] = {}
        for record in within_window:
            latest_by_identity[record.repo, record.issue] = record

        return tuple(latest_by_identity.values())
