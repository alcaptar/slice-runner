from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.finding import Finding
from slice_runner.domain.prior_finding_ruling import PriorFindingRuling, PriorFindingState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.verdict import Verdict
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema


class FindingPayload(ContractModel):
    rule: str
    path: str
    severity: Severity
    evidence: str
    detail: str
    line: int | None = Field(default=None, strict=True)

    @classmethod
    def contract_keys(cls) -> set[str]:
        return set(cls.model_fields)

    @classmethod
    def from_domain(cls, finding: Finding) -> Self:
        return cls.model_validate(
            {
                "rule": finding.rule,
                "path": finding.path,
                "severity": finding.severity,
                "evidence": finding.evidence,
                "detail": finding.detail,
                "line": finding.line,
            }
        )

    def to_domain(self) -> Finding:
        return Finding(
            rule=self.rule,
            path=self.path,
            severity=self.severity,
            evidence=self.evidence,
            detail=self.detail,
            line=self.line,
        )


class PriorFindingRulingPayload(ContractModel):
    id: str
    state: PriorFindingState
    reason: str = ""

    @classmethod
    def contract_keys(cls) -> set[str]:
        return set(cls.model_fields)

    @classmethod
    def from_domain(cls, ruling: PriorFindingRuling) -> Self:
        return cls.model_validate({"id": ruling.id, "state": ruling.state, "reason": ruling.reason})

    def to_domain(self) -> PriorFindingRuling:
        return PriorFindingRuling(id=self.id, state=self.state, reason=self.reason)


class VerdictPayload(ContractModel):
    ruling: Ruling
    findings: list[FindingPayload]
    prior_rulings: list[PriorFindingRulingPayload] = Field(default_factory=list)

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the judge did not emit the verdict of the rubric", InvalidVerdictError)

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate(
            {
                "ruling": verdict.ruling,
                "findings": [FindingPayload.from_domain(finding) for finding in verdict.findings],
                "prior_rulings": [PriorFindingRulingPayload.from_domain(ruling) for ruling in verdict.prior_rulings],
            }
        )

    def to_domain(self) -> Verdict:
        return Verdict(
            ruling=self.ruling,
            findings=tuple(finding.to_domain() for finding in self.findings),
            prior_rulings=tuple(ruling.to_domain() for ruling in self.prior_rulings),
        )
