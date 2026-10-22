from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.infrastructure.closed_as import ClosedAs
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.diff_stats_payload import DiffStatsPayload
from slice_runner.infrastructure.discarded_call_payload import DiscardedCallPayload

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.recorded_spend import RecordedSpend
    from slice_runner.domain.severity_count import SeverityCount


class RecordedSpendPayload(ContractModel):
    cost_usd: float
    turns: int
    duration_ms: int
    cache_read_tokens: int
    input_tokens: int
    output_tokens: int

    @classmethod
    def from_domain(cls, spend: RecordedSpend) -> Self:
        return cls(
            cost_usd=spend.cost_usd,
            turns=spend.turns,
            duration_ms=spend.duration_ms,
            cache_read_tokens=spend.cache_read_tokens,
            input_tokens=spend.input_tokens,
            output_tokens=spend.output_tokens,
        )


class SeverityCountPayload(ContractModel):
    high: int
    medium: int
    low: int

    @classmethod
    def from_domain(cls, count: SeverityCount) -> Self:
        return cls(high=count.high, medium=count.medium, low=count.low)


class ClosedSliceRecordPayload(ContractModel):
    ts: str
    repo: str
    issue: int
    slice_id: str
    name: str
    state: ClosedAs
    findings: SeverityCountPayload
    findings_of_the_last_round: SeverityCountPayload
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    verify_discards: int
    implement_discards: int
    discarded_call: DiscardedCallPayload | None = None
    ci_indeterminate_cause: CiIndeterminateCause | None = None
    spend: RecordedSpendPayload | None = None
    variant: str | None = None
    models: tuple[str, ...] = ()
    declared_debt: int | None = None
    diff: DiffStatsPayload | None = None
    budgets: dict[str, object]
    models_by_role: dict[str, object]
    effort_by_role: dict[str, object] | None = None

    @classmethod
    def from_domain(cls, record: ClosedSliceRecord) -> Self:
        return cls.model_validate(
            {
                "ts": record.ts.isoformat(),
                "repo": record.repo,
                "issue": record.issue,
                "slice_id": record.slice_id,
                "name": record.name,
                "state": ClosedAs.of(record.closure),
                "findings": SeverityCountPayload.from_domain(record.findings),
                "findings_of_the_last_round": SeverityCountPayload.from_domain(record.findings_of_the_last_round),
                "implement_retries": record.implement_retries,
                "control_retries": record.control_retries,
                "ci_retries": record.ci_retries,
                "verify_retries": record.verify_retries,
                "verify_discards": record.verify_discards,
                "implement_discards": record.implement_discards,
                "discarded_call": DiscardedCallPayload.from_domain(record.discarded_call)
                if record.discarded_call is not None
                else None,
                "ci_indeterminate_cause": record.ci_indeterminate_cause,
                "spend": RecordedSpendPayload.from_domain(record.spend) if record.spend is not None else None,
                "variant": record.variant,
                "models": record.models,
                "declared_debt": record.declared_debt,
                "diff": DiffStatsPayload.from_domain(record.diff) if record.diff is not None else None,
                "budgets": record.budgets,
                "models_by_role": record.models_by_role,
                "effort_by_role": record.effort_by_role,
            }
        )

    def to_contract(self) -> dict[str, object]:
        return {**super().to_contract(), "effort_by_role": self.effort_by_role}
