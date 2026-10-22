from __future__ import annotations

from typing import Self

from slice_runner.domain.diff_stats import DiffStats
from slice_runner.infrastructure.contract_model import ContractModel


class DiffStatsPayload(ContractModel):
    files_changed: int
    lines_added: int
    lines_deleted: int

    @classmethod
    def from_domain(cls, stats: DiffStats) -> Self:
        return cls.model_validate(
            {
                "files_changed": stats.files_changed,
                "lines_added": stats.lines_added,
                "lines_deleted": stats.lines_deleted,
            }
        )

    def to_domain(self) -> DiffStats:
        return DiffStats(
            files_changed=self.files_changed, lines_added=self.lines_added, lines_deleted=self.lines_deleted
        )
