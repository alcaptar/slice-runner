from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.prior_finding_ruling import PriorFindingRuling


@dataclass(frozen=True, kw_only=True, slots=True)
class Verdict:
    BLOCKING: ClassVar[frozenset[Severity]] = frozenset({Severity.HIGH, Severity.MEDIUM})

    ruling: Ruling
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    prior_rulings: tuple[PriorFindingRuling, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        blocking = [finding for finding in self.findings if finding.severity in self.BLOCKING]
        if self.ruling is Ruling.PASS and blocking:
            raise InvalidVerdictError(
                f"a {Ruling.PASS} with {len(blocking)} finding(s) of severity {Severity.HIGH} or {Severity.MEDIUM} "
                f"contradicts the rubric: one finding of either severity means {Ruling.FAIL}"
            )

    def count_of(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)
