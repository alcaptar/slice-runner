from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from slice_runner.domain.closed_slice_record import ClosedSliceRecord
from slice_runner.domain.exceptions import UnreadableMetricsLogError
from slice_runner.domain.recorded_spend import RecordedSpend
from slice_runner.domain.severity_count import SeverityCount
from slice_runner.infrastructure.metrics_entry_payload import (
    DurableCiIndeterminateCause,
    DurableClosure,
    MetricsEntryPayload,
)

if TYPE_CHECKING:
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.infrastructure.corpus_verdict_payload import SeverityCountPayload
    from slice_runner.infrastructure.spend_payload import SpendPayload


class MetricsLedgerEntry:
    @classmethod
    def of(cls, payload: MetricsEntryPayload) -> ClosedSliceRecord:
        return ClosedSliceRecord(
            ts=cls._timestamp(payload.ts),
            repo=payload.repo,
            issue=payload.issue,
            slice_id=payload.slice_id,
            name=payload.name,
            closure=DurableClosure.closure_of(verdict=payload.verdict, ci=payload.ci),
            findings=cls._severity_count(payload.findings),
            findings_of_the_last_round=cls._severity_count(payload.findings_of_the_last_round),
            implement_retries=payload.implement_retries,
            control_retries=payload.control_retries,
            ci_retries=payload.ci_retries,
            verify_retries=payload.verify_retries,
            verify_discards=payload.verify_discards,
            implement_discards=payload.implement_discards,
            discarded_call=cls._discarded_call(payload),
            ci_indeterminate_cause=cls._ci_indeterminate_cause(payload.ci_indeterminate_cause),
            spend=cls._spend(payload.harness) if payload.harness is not None else None,
            variant=payload.variant,
            models=tuple(payload.harness.models) if payload.harness is not None else (),
            declared_debt=payload.declared_debt,
            diff=payload.diff.to_domain() if payload.diff is not None else None,
            budgets=payload.budgets,
            models_by_role=payload.models_by_role,
            effort_by_role=payload.effort_by_role,
        )

    @staticmethod
    def _timestamp(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise UnreadableMetricsLogError(f"the metrics log has an unreadable timestamp: {error}") from error

    @staticmethod
    def _discarded_call(payload: MetricsEntryPayload) -> DiscardedCall | None:
        return payload.discarded_call.to_domain() if payload.discarded_call is not None else None

    @staticmethod
    def _ci_indeterminate_cause(cause: DurableCiIndeterminateCause | None) -> CiIndeterminateCause | None:
        return cause.to_domain() if cause is not None else None

    @staticmethod
    def _spend(harness: SpendPayload) -> RecordedSpend:
        return RecordedSpend(
            cost_usd=harness.cost_usd,
            turns=harness.turns,
            duration_ms=harness.duration_ms,
            cache_read_tokens=harness.cache_read_tokens,
            input_tokens=harness.input_tokens,
            output_tokens=harness.output_tokens,
        )

    @staticmethod
    def _severity_count(counts: SeverityCountPayload) -> SeverityCount:
        return SeverityCount(high=counts.high, medium=counts.medium, low=counts.low)
