from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding

_INTENTION_HEADING = "## Intencion"
_INFERRED_INTENTION_HEADING = "## Intencion (inferida del issue, no declarada)"
_CRITERIA_HEADING = "## Criterios de aceptacion cumplidos"
_DEBT_HEADING = "## Deuda aceptada"
_DEVIATIONS_HEADING = "## Decisiones de diseno no seguidas"
_PARDONED_FINDINGS_LABEL = "Hallazgos que el juez dejo pasar sin corregir:"


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestBody:
    intention: str
    criteria: tuple[str, ...]
    debt: tuple[str, ...]
    findings: tuple[Finding, ...]
    deviations: tuple[str, ...]
    subissue: int

    def rendered(self) -> str:
        sections = [
            self._section(self._intention_heading, self.intention),
            self._section(_CRITERIA_HEADING, self._bullets(self.criteria)),
            *([self._section(_DEBT_HEADING, self._debt_section_body())] if self.debt or self.findings else []),
            *([self._section(_DEVIATIONS_HEADING, self._bullets(self.deviations))] if self.deviations else []),
            f"Closes #{self.subissue}",
        ]

        return "\n\n".join(sections)

    @property
    def _intention_heading(self) -> str:
        return _INTENTION_HEADING if self.intention.strip() else _INFERRED_INTENTION_HEADING

    def _debt_section_body(self) -> str:
        groups = [group for group in (self._declared_debt(), self._pardoned_findings()) if group]

        return "\n\n".join(groups)

    def _declared_debt(self) -> str:
        return self._bullets(self.debt) if self.debt else ""

    def _pardoned_findings(self) -> str:
        if not self.findings:
            return ""

        lines = tuple(self._finding_line(finding) for finding in self.findings)

        return f"{_PARDONED_FINDINGS_LABEL}\n{self._bullets(lines)}"

    @staticmethod
    def _section(heading: str, text: str) -> str:
        return f"{heading}\n{text}"

    @staticmethod
    def _bullets(lines: tuple[str, ...]) -> str:
        return "\n".join(f"- {line}" for line in lines)

    @staticmethod
    def _finding_line(finding: Finding) -> str:
        return f"{finding.severity}: {finding.rule} - {finding.detail} ({finding.path})"
