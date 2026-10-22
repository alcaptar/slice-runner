from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_trace import CallTrace, HarnessCall
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.durable_ledger import ReadableDurableLedger
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload

if TYPE_CHECKING:
    from collections.abc import Iterator

    from slice_runner.domain.clock import Clock
    from slice_runner.domain.step import Step


class LocalCallTrace(CallTrace):
    LEDGER: ClassVar[str] = "calls"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._ledger: ReadableDurableLedger[HarnessCallPayload] = ReadableDurableLedger(
            name=self.LEDGER, row=HarnessCallPayload
        )

    def record(self, call: HarnessCall) -> None:
        payload = HarnessCallPayload.from_call(call, ts=self._clock.now().isoformat())
        self._ledger.append(payload)

    def sessions_of(self, *, repo: str, issue: int, slice_id: str, step: Step) -> tuple[str, ...]:
        coordinates = SliceCoordinates(repo=repo, issue=issue, slice_id=CanonicalSliceId.of_text(slice_id))

        return tuple(call.session for call in self._mine(coordinates) if call.step == step)

    def calls_of(self, *, repo: str, issue: int, slice_id: str) -> tuple[HarnessCall, ...]:
        coordinates = SliceCoordinates(repo=repo, issue=issue, slice_id=CanonicalSliceId.of_text(slice_id))

        return tuple(
            HarnessCall(coordinates=coordinates, step=call.step, session=call.session)
            for call in self._mine(coordinates)
        )

    def _mine(self, coordinates: SliceCoordinates) -> Iterator[HarnessCallPayload]:
        return self._ledger.rows_where(lambda data: HarnessCallPayload.may_belong_to(data, coordinates))
