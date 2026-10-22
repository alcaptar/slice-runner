from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.exceptions import UnreadableCorpusError
from slice_runner.domain.severity import Severity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.diff_stats_payload import DiffStatsPayload
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.stamped_row import StampedRow
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.verdict import Verdict


class SeverityCountPayload(ContractModel):
    high: int
    medium: int
    low: int

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate(
            {
                "high": verdict.count_of(Severity.HIGH),
                "medium": verdict.count_of(Severity.MEDIUM),
                "low": verdict.count_of(Severity.LOW),
            }
        )


class CorpusVerdictPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableCorpusError

    verify_round: int
    session: str
    verdict: VerdictPayload
    severity_counts: SeverityCountPayload
    diff_stats: DiffStatsPayload
    prior_findings_given: int | None = None
    diff_fingerprint: str | None = None

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, entry: CorpusEntry, *, ts: str) -> Self:
        coordinates = SliceCoordinates(
            repo=entry.repo, issue=entry.issue, slice_id=CanonicalSliceId.of_text(entry.slice_id)
        )

        return cls._stamped(
            coordinates,
            ts=ts,
            verify_round=entry.verify_round,
            session=entry.session,
            verdict=VerdictPayload.from_domain(entry.verdict),
            severity_counts=SeverityCountPayload.from_domain(entry.verdict),
            diff_stats=DiffStatsPayload.from_domain(entry.diff.stats),
            prior_findings_given=entry.prior_findings_given,
            diff_fingerprint=entry.diff.fingerprint,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the corpus verdict log line is not one this program wrote in this generation", cls.UNREADABLE
        )
