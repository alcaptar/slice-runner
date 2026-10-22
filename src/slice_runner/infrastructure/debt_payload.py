from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.exceptions import UnreadableDebtLedgerError
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.debt_entry import DebtEntry


class DebtPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableDebtLedgerError

    left_out: tuple[str, ...]

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, entry: DebtEntry, *, ts: str) -> Self:
        return cls._stamped(entry.coordinates, ts=ts, left_out=entry.left_out)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the debt ledger line is not one this program wrote in this generation", cls.UNREADABLE
        )
