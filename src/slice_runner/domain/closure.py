from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import InvalidClosureError
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.closing_reason import ClosingReason


@dataclass(frozen=True, kw_only=True, slots=True)
class Closure:
    state: RunState
    reason: ClosingReason | None = None

    def __post_init__(self) -> None:
        match self.state:
            case RunState.OPEN | RunState.MERGED:
                self._refuse_a_reason()
            case RunState.BLOCKED | RunState.ABORTED:
                self._refuse_a_missing_or_foreign_reason()

    @classmethod
    def open(cls) -> Closure:
        return cls(state=RunState.OPEN)

    @classmethod
    def merged(cls) -> Closure:
        return cls(state=RunState.MERGED)

    @classmethod
    def because_of(cls, reason: ClosingReason) -> Closure:
        return cls(state=reason.closes_as, reason=reason)

    @property
    def publishes_the_findings(self) -> bool:
        return self.reason is not None and self.reason.publishes_the_findings

    def _refuse_a_reason(self) -> None:
        if self.reason is not None:
            raise InvalidClosureError(f"a run in state `{self.state}` has no closing reason, got `{self.reason}`")

    def _refuse_a_missing_or_foreign_reason(self) -> None:
        if self.reason is None:
            raise InvalidClosureError(f"a run in state `{self.state}` needs a closing reason")
        if self.reason.closes_as is not self.state:
            raise InvalidClosureError(
                f"the reason `{self.reason}` closes a run as `{self.reason.closes_as}`, not `{self.state}`"
            )
