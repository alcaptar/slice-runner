from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.protected_branch import ProtectedBranch


class _Verdict(StrEnum):
    OK = "ok"
    PROTECTED = "protected"
    MISMATCHED = "mismatched"


@dataclass(frozen=True, kw_only=True, slots=True)
class BranchStanding:
    standing_on: str
    declared: str
    verdict: _Verdict

    @classmethod
    def of(cls, *, standing_on: str, declared: str) -> BranchStanding:
        if ProtectedBranch.protects(standing_on):
            verdict = _Verdict.PROTECTED
        elif standing_on != declared:
            verdict = _Verdict.MISMATCHED
        else:
            verdict = _Verdict.OK

        return cls(standing_on=standing_on, declared=declared, verdict=verdict)

    def raise_unless_ok(self, *, action: str) -> None:
        match self.verdict:
            case _Verdict.PROTECTED:
                raise ProtectedBranchError(
                    f"refusing to {action} on {self.standing_on}: a slice is delivered from its own branch"
                )
            case _Verdict.MISMATCHED:
                raise BranchMismatchError(
                    f"the worktree stands on {self.standing_on} and the slice declared {self.declared}: "
                    f"the {action} would land on a different branch"
                )
            case _Verdict.OK:
                pass
