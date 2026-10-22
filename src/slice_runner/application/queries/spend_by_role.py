from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.role_spend import RoleSpend

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class SpendByRoleParams:
    records: tuple[ClosedSliceRecord, ...]


class SpendByRole:
    def __init__(self, *, trace: CallTrace, spend_log: CallSpendLog) -> None:
        self._trace = trace
        self._spend_log = spend_log

    def execute(self, params: SpendByRoleParams) -> tuple[RoleSpend, ...]:
        sessions_of_the_step: dict[Step, list[str]] = {}
        for record in params.records:
            for call in self._trace.calls_of(repo=record.repo, issue=record.issue, slice_id=record.slice_id):
                sessions_of_the_step.setdefault(call.step, []).append(call.session)

        return tuple(
            RoleSpend(step=step, spend=self._spend_log.spend_of(tuple(sessions)))
            for step, sessions in sessions_of_the_step.items()
        )
