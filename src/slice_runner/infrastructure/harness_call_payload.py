from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.call_trace import HarnessCall


class HarnessCallPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableCallTraceError

    step: Step
    session: str

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_call(cls, call: HarnessCall, *, ts: str) -> Self:
        return cls._stamped(call.coordinates, ts=ts, step=call.step, session=call.session)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the call trace line is not one this program wrote in this generation", cls.UNREADABLE
        )
