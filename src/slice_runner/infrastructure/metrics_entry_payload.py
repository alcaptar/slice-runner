from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.discarded_call import DiscardedCall
from slice_runner.domain.exceptions import RunNotClosedError, UnreadableMetricsLogError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.corpus_verdict_payload import SeverityCountPayload
from slice_runner.infrastructure.diff_stats_payload import DiffStatsPayload
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice


class DurableVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED_UNCHANGED_DIFF = "blocked-unchanged-diff"
    BLOCKED_CONTROLS = "blocked-controls"
    BLOCKED_HYGIENE = "blocked-hygiene"
    BLOCKED_WORKTREE = "blocked-worktree"
    BLOCKED_LEFTOVER_WORKTREE = "blocked-leftover-worktree"
    ABORTED_BUDGET = "aborted-budget"
    ABORTED_UNMEASURED_CALL = "aborted-unmeasured-call"


class DurableCi(StrEnum):
    GREEN = "green"
    RED = "red"
    NONE = "none"
    CONFLICT = "conflict"


class DurableDiscardCause(StrEnum):
    INCOHERENT_VERDICT = "incoherent-verdict"
    FAILED_CALL = "failed-call"
    NO_STRUCTURED_OUTPUT = "no-structured-output"

    @classmethod
    def of(cls, cause: DiscardCause) -> DurableDiscardCause:
        match cause:
            case DiscardCause.INCOHERENT_VERDICT:
                return cls.INCOHERENT_VERDICT
            case DiscardCause.FAILED_CALL:
                return cls.FAILED_CALL
            case DiscardCause.NO_STRUCTURED_OUTPUT:
                return cls.NO_STRUCTURED_OUTPUT

    def to_domain(self) -> DiscardCause:
        match self:
            case DurableDiscardCause.INCOHERENT_VERDICT:
                return DiscardCause.INCOHERENT_VERDICT
            case DurableDiscardCause.FAILED_CALL:
                return DiscardCause.FAILED_CALL
            case DurableDiscardCause.NO_STRUCTURED_OUTPUT:
                return DiscardCause.NO_STRUCTURED_OUTPUT


class DurableCiIndeterminateCause(StrEnum):
    COMMAND_FAILED = "command-failed"
    UNREADABLE_RESPONSE = "unreadable-response"

    @classmethod
    def of(cls, cause: CiIndeterminateCause) -> DurableCiIndeterminateCause:
        match cause:
            case CiIndeterminateCause.COMMAND_FAILED:
                return cls.COMMAND_FAILED
            case CiIndeterminateCause.UNREADABLE_RESPONSE:
                return cls.UNREADABLE_RESPONSE

    def to_domain(self) -> CiIndeterminateCause:
        match self:
            case DurableCiIndeterminateCause.COMMAND_FAILED:
                return CiIndeterminateCause.COMMAND_FAILED
            case DurableCiIndeterminateCause.UNREADABLE_RESPONSE:
                return CiIndeterminateCause.UNREADABLE_RESPONSE


@dataclass(frozen=True, kw_only=True, slots=True)
class DurableClosure:
    verdict: DurableVerdict
    ci: DurableCi

    _VERDICTS_WITH_NO_CI: ClassVar[dict[ClosingReason, DurableVerdict]] = {
        ClosingReason.JUDGE: DurableVerdict.FAIL,
        ClosingReason.CONTROLS: DurableVerdict.BLOCKED_CONTROLS,
        ClosingReason.WORKTREE: DurableVerdict.BLOCKED_WORKTREE,
        ClosingReason.BUDGET: DurableVerdict.ABORTED_BUDGET,
        ClosingReason.UNMEASURED_CALL: DurableVerdict.ABORTED_UNMEASURED_CALL,
    }

    _REASONS_WITH_NO_CI: ClassVar[dict[DurableVerdict, ClosingReason]] = {
        DurableVerdict.FAIL: ClosingReason.JUDGE,
        DurableVerdict.BLOCKED_UNCHANGED_DIFF: ClosingReason.JUDGE,
        DurableVerdict.BLOCKED_CONTROLS: ClosingReason.CONTROLS,
        DurableVerdict.BLOCKED_HYGIENE: ClosingReason.CONTROLS,
        DurableVerdict.BLOCKED_WORKTREE: ClosingReason.WORKTREE,
        DurableVerdict.BLOCKED_LEFTOVER_WORKTREE: ClosingReason.WORKTREE,
        DurableVerdict.ABORTED_BUDGET: ClosingReason.BUDGET,
        DurableVerdict.ABORTED_UNMEASURED_CALL: ClosingReason.UNMEASURED_CALL,
    }
    _MERGED_CLOSURES: ClassVar[dict[DurableCi, Closure]] = {
        DurableCi.GREEN: Closure.merged(),
        DurableCi.RED: Closure.because_of(ClosingReason.CI_RED),
        DurableCi.NONE: Closure.because_of(ClosingReason.CI_INDETERMINATE),
        DurableCi.CONFLICT: Closure.because_of(ClosingReason.CI_CONFLICT),
    }

    @classmethod
    def of(cls, closure: Closure) -> DurableClosure:
        match closure.state:
            case RunState.MERGED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.GREEN)
            case RunState.BLOCKED | RunState.ABORTED:
                return cls._of_the_reason(closure.reason)
            case RunState.OPEN:
                raise RunNotClosedError(
                    f"a run in state {RunState.OPEN} has no verdict to record: "
                    f"the durable log is one line per closed slice"
                )

    @classmethod
    def _of_the_reason(cls, reason: ClosingReason | None) -> DurableClosure:
        match reason:
            case ClosingReason.CI_RED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.RED)
            case ClosingReason.CI_INDETERMINATE:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.NONE)
            case ClosingReason.CI_CONFLICT:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.CONFLICT)
            case (
                ClosingReason.JUDGE
                | ClosingReason.CONTROLS
                | ClosingReason.WORKTREE
                | ClosingReason.BUDGET
                | ClosingReason.UNMEASURED_CALL
            ):
                return cls(verdict=cls._VERDICTS_WITH_NO_CI[reason], ci=DurableCi.NONE)
            case None:
                raise RunNotClosedError("a blocked or aborted run without a closing reason has no verdict to record")

    @classmethod
    def closure_of(cls, *, verdict: DurableVerdict, ci: DurableCi) -> Closure:
        match verdict:
            case DurableVerdict.PASS:
                return cls._MERGED_CLOSURES[ci]
            case (
                DurableVerdict.FAIL
                | DurableVerdict.BLOCKED_UNCHANGED_DIFF
                | DurableVerdict.BLOCKED_CONTROLS
                | DurableVerdict.BLOCKED_HYGIENE
                | DurableVerdict.BLOCKED_WORKTREE
                | DurableVerdict.BLOCKED_LEFTOVER_WORKTREE
                | DurableVerdict.ABORTED_BUDGET
                | DurableVerdict.ABORTED_UNMEASURED_CALL
            ):
                return Closure.because_of(cls._REASONS_WITH_NO_CI[verdict])


class DiscardedCallPayload(ContractModel):
    step: Step
    cause: DurableDiscardCause
    reason: str

    @classmethod
    def from_domain(cls, discarded: DiscardedCall) -> Self:
        return cls.model_validate(
            {"step": discarded.step, "cause": DurableDiscardCause.of(discarded.cause), "reason": discarded.reason}
        )

    def to_domain(self) -> DiscardedCall:
        return DiscardedCall(step=self.step, cause=self.cause.to_domain(), reason=self.reason)


class MetricsEntryPayload(StampedRow, ReadableLedgerRow):
    VARIANT: ClassVar[str] = "program"
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableMetricsLogError

    name: str
    verdict: DurableVerdict
    ci: DurableCi
    findings: SeverityCountPayload
    findings_of_the_last_round: SeverityCountPayload
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    verify_discards: int
    understand_discards: int | None = None
    implement_discards: int
    harness: SpendPayload | None = None
    discarded_call: DiscardedCallPayload | None = None
    ci_indeterminate_cause: DurableCiIndeterminateCause | None = None
    variant: str
    declared_debt: int | None = None
    diff: DiffStatsPayload | None = None
    worktree_retirement: WorktreeRetirement = WorktreeRetirement.NOT_MOUNTED
    worktree: str | None = None
    budgets: dict[str, object]
    models_by_role: dict[str, object]
    effort_by_role: dict[str, object] | None = None

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, closed: ClosedSlice, *, ts: str) -> Self:
        closure = DurableClosure.of(closed.closure)
        spend = closed.spend
        coordinates = SliceCoordinates(
            repo=closed.repo, issue=closed.issue, slice_id=CanonicalSliceId.of_text(closed.slice_id)
        )
        return cls._stamped(
            coordinates,
            ts=ts,
            **{
                "name": closed.name,
                "verdict": closure.verdict,
                "ci": closure.ci,
                "findings": SeverityCountPayload.model_validate(
                    {
                        "high": closed.count_findings(Severity.HIGH),
                        "medium": closed.count_findings(Severity.MEDIUM),
                        "low": closed.count_findings(Severity.LOW),
                    }
                ),
                "findings_of_the_last_round": SeverityCountPayload.model_validate(
                    {
                        "high": closed.count_findings_of_the_last_round(Severity.HIGH),
                        "medium": closed.count_findings_of_the_last_round(Severity.MEDIUM),
                        "low": closed.count_findings_of_the_last_round(Severity.LOW),
                    }
                ),
                "implement_retries": closed.run.implement_retries,
                "control_retries": closed.run.control_retries,
                "ci_retries": closed.run.ci_retries,
                "verify_retries": closed.run.verify_retries,
                "verify_discards": closed.run.verify_discards,
                "implement_discards": closed.run.implement_discards,
                "harness": SpendPayload.from_domain(spend) if spend.measured else None,
                "discarded_call": DiscardedCallPayload.from_domain(closed.run.discarded_call)
                if closed.run.discarded_call is not None
                else None,
                "ci_indeterminate_cause": DurableCiIndeterminateCause.of(closed.ci_indeterminate_cause)
                if closed.ci_indeterminate_cause
                else None,
                "variant": cls.VARIANT,
                "declared_debt": len(closed.debt.left_out) if closed.debt.declared else None,
                "diff": DiffStatsPayload.from_domain(closed.diff_stats) if closed.diff_stats is not None else None,
                "worktree_retirement": closed.worktree_retirement,
                "worktree": closed.worktree if closed.worktree_retirement.kept else None,
                "budgets": asdict(closed.budgets),
                "models_by_role": {"implement": closed.models.implement, "verify": closed.models.verify},
                "effort_by_role": {
                    "implement": closed.models.implement_effort,
                    "verify": closed.models.verify_effort,
                },
            },
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the metrics log line is not one this program wrote in this generation", cls.UNREADABLE
        )
