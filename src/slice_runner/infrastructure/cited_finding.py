from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class CitedFinding:
    @staticmethod
    def of(finding: Finding) -> str:
        where = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path

        return f"[{finding.severity}] {finding.rule} en {where}: {finding.evidence} (detalle: {finding.detail})"
