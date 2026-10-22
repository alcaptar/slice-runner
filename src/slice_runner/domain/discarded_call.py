from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.discard_cause import DiscardCause

if TYPE_CHECKING:
    from slice_runner.domain.exceptions import MeasuredCallError
    from slice_runner.domain.step import Step

_REASON_LIMIT = 200


@dataclass(frozen=True, kw_only=True, slots=True)
class DiscardedCall:
    step: Step
    cause: DiscardCause
    reason: str

    @classmethod
    def of_the_rejection(cls, step: Step, rejection: MeasuredCallError) -> DiscardedCall:
        return cls(step=step, cause=DiscardCause.of_the_rejection(rejection), reason=str(rejection)[:_REASON_LIMIT])
