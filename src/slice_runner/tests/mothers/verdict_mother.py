from __future__ import annotations

from slice_runner.domain.finding import Finding
from slice_runner.domain.prior_finding_ruling import PriorFindingRuling, PriorFindingState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.verdict import Verdict


class FindingMother:
    @staticmethod
    def without_line(
        *,
        rule: str = "cobertura-capa",
        path: str = "src/x.py",
        severity: Severity = Severity.HIGH,
        evidence: str = "the acceptance criterion has no test",
    ) -> Finding:
        return Finding(
            rule=rule,
            path=path,
            severity=severity,
            evidence=evidence,
            detail="the test that accredits it is missing",
        )

    @staticmethod
    def with_line(line: int = 42) -> Finding:
        return Finding(
            rule="convenciones",
            path="src/x.py",
            severity=Severity.MEDIUM,
            evidence="prose in a `.py`",
            detail="the why lives in the pull request body",
            line=line,
        )

    @staticmethod
    def with_a_very_long_detail() -> Finding:
        return Finding(
            rule="cobertura-capa",
            path="src/y.py",
            severity=Severity.HIGH,
            evidence="a finding with a detail nobody should truncate",
            detail="d" * 20000,
            line=7,
        )

    @staticmethod
    def low_severity(*, path: str = "src/x.py", line: int | None = None) -> Finding:
        return Finding(
            rule="nombrado",
            path=path,
            severity=Severity.LOW,
            evidence="una constante sin nombre",
            detail="queda para otra vuelta, no bloquea la entrega",
            line=line,
        )


class PriorFindingRulingMother:
    @staticmethod
    def fixed(*, id: str = "f1") -> PriorFindingRuling:
        return PriorFindingRuling(id=id, state=PriorFindingState.FIXED)

    @staticmethod
    def retired(*, id: str = "f1", reason: str = "el criterio que citaba ya no existe") -> PriorFindingRuling:
        return PriorFindingRuling(id=id, state=PriorFindingState.RETIRED, reason=reason)


class VerdictMother:
    @staticmethod
    def passing() -> Verdict:
        return Verdict(ruling=Ruling.PASS)

    @staticmethod
    def failing(*findings: Finding) -> Verdict:
        return Verdict(ruling=Ruling.FAIL, findings=findings or (FindingMother.without_line(),))

    @staticmethod
    def passing_with(*findings: Finding) -> Verdict:
        return Verdict(ruling=Ruling.PASS, findings=findings or (FindingMother.low_severity(),))

    @staticmethod
    def pronouncing_on(*prior_rulings: PriorFindingRuling, findings: tuple[Finding, ...] = ()) -> Verdict:
        return Verdict(
            ruling=Ruling.PASS,
            findings=findings,
            prior_rulings=prior_rulings or (PriorFindingRulingMother.fixed(),),
        )
