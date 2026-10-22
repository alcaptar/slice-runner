from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.closed_slice_record import ClosedSliceRecord
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.recorded_spend import RecordedSpend
from slice_runner.domain.severity_count import SeverityCount

if TYPE_CHECKING:
    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discarded_call import DiscardedCall


class ClosedSliceRecordMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 134
    SLICE_ID: ClassVar[str] = "slice-06"
    NAME: ClassVar[str] = "el-analisis-y-la-vista-son-un-comando"
    TS: ClassVar[datetime] = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
    NO_FINDINGS: ClassVar[SeverityCount] = SeverityCount(high=0, medium=0, low=0)
    DEFAULT_SPEND: ClassVar[RecordedSpend] = RecordedSpend(
        cost_usd=0.4, turns=10, duration_ms=50000, cache_read_tokens=200000, input_tokens=15, output_tokens=1200
    )

    @classmethod
    def merged(cls) -> ClosedSliceRecord:
        return cls._record(Closure.merged())

    @classmethod
    def closed_as(cls, closure: Closure) -> ClosedSliceRecord:
        return cls._record(closure)

    @classmethod
    def merged_at(cls, ts: datetime) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), ts=ts)

    @classmethod
    def merged_in(cls, repo: str) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), repo=repo)

    @classmethod
    def merged_for_issue(cls, issue: int) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), issue=issue)

    @classmethod
    def merged_with_effort(cls, effort_by_role: dict[str, object] | None) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), effort_by_role=effort_by_role)

    @classmethod
    def merged_measuring(cls, spend: RecordedSpend) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), spend=spend)

    @classmethod
    def merged_measuring_nothing(cls) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), spend=None)

    @classmethod
    def merged_measuring_the_diff(cls, diff: DiffStats) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), diff=diff)

    @classmethod
    def merged_after_retrying(cls, *, implement_retries: int, verify_retries: int) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), implement_retries=implement_retries, verify_retries=verify_retries)

    @classmethod
    def merged_discarding_because_of(cls, discarded: DiscardedCall | None) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), discarded_call=discarded)

    @classmethod
    def merged_after_discarding_harness_calls(cls, *, implement_discards: int) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), implement_discards=implement_discards)

    @classmethod
    def blocked_indeterminate_because_of(cls, cause: CiIndeterminateCause | None) -> ClosedSliceRecord:
        return cls._record(Closure.because_of(ClosingReason.CI_INDETERMINATE), ci_indeterminate_cause=cause)

    @classmethod
    def merged_declaring_no_model_and_no_variant(cls) -> ClosedSliceRecord:
        return cls._record(Closure.merged(), variant=None, models=())

    @classmethod
    def _record(
        cls,
        closure: Closure,
        *,
        ts: datetime | None = None,
        repo: str | None = None,
        issue: int | None = None,
        slice_id: str | None = None,
        spend: RecordedSpend | None = DEFAULT_SPEND,
        diff: DiffStats | None = None,
        implement_retries: int = 0,
        verify_retries: int = 0,
        discarded_call: DiscardedCall | None = None,
        ci_indeterminate_cause: CiIndeterminateCause | None = None,
        implement_discards: int = 0,
        variant: str | None = "program",
        models: tuple[str, ...] = ("claude-sonnet-5",),
        effort_by_role: dict[str, object] | None = None,
    ) -> ClosedSliceRecord:
        return ClosedSliceRecord(
            ts=ts or cls.TS,
            repo=repo or cls.REPO,
            issue=cls.ISSUE if issue is None else issue,
            slice_id=slice_id or cls.SLICE_ID,
            name=cls.NAME,
            closure=closure,
            findings=cls.NO_FINDINGS,
            findings_of_the_last_round=cls.NO_FINDINGS,
            implement_retries=implement_retries,
            control_retries=0,
            ci_retries=0,
            verify_retries=verify_retries,
            verify_discards=0,
            implement_discards=implement_discards,
            discarded_call=discarded_call,
            ci_indeterminate_cause=ci_indeterminate_cause,
            spend=spend,
            variant=variant,
            models=models,
            declared_debt=None,
            diff=diff,
            budgets={},
            models_by_role={},
            effort_by_role=effort_by_role,
        )
