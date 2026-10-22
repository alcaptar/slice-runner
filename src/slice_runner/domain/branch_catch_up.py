from __future__ import annotations

from dataclasses import dataclass, field

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome


@dataclass(frozen=True, kw_only=True, slots=True)
class BranchCatchUp:
    outcome: BranchCatchUpOutcome
    conflicting_paths: tuple[str, ...] = field(default=())

    @classmethod
    def caught_up(cls) -> BranchCatchUp:
        return cls(outcome=BranchCatchUpOutcome.CAUGHT_UP)

    @classmethod
    def conflicting(cls, *, paths: tuple[str, ...]) -> BranchCatchUp:
        return cls(outcome=BranchCatchUpOutcome.CONFLICTING, conflicting_paths=paths)
