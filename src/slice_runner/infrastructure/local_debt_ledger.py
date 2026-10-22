from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.debt_ledger import DebtDeclaration, DebtLedger
from slice_runner.infrastructure.debt_payload import DebtPayload
from slice_runner.infrastructure.durable_ledger import ReadableDurableLedger

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.debt_entry import DebtEntry
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class LocalDebtLedger(DebtLedger):
    LEDGER: ClassVar[str] = "debt"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._entries: ReadableDurableLedger[DebtPayload] = ReadableDurableLedger(name=self.LEDGER, row=DebtPayload)

    def record(self, entry: DebtEntry) -> None:
        ts = self._clock.now().isoformat()
        self._entries.append(DebtPayload.from_domain(entry, ts=ts))

    def declarations_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[DebtDeclaration, ...]:
        return tuple(
            DebtDeclaration(left_out=row.left_out)
            for row in self._entries.rows_where(lambda data: DebtPayload.may_belong_to(data, coordinates))
        )
