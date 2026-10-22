from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.exceptions import UnreadableCallSpendLogError
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import HarnessCallSpend


class CallSpendPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableCallSpendLogError

    session: str
    spend: SpendPayload

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_call(cls, call: HarnessCallSpend, *, ts: str) -> Self:
        return cls._stamped(call.coordinates, ts=ts, session=call.session, spend=SpendPayload.from_domain(call.spend))

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the spend log line is not one this program wrote in this generation", cls.UNREADABLE
        )
