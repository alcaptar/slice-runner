from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus import Corpus, JudgedRound
from slice_runner.infrastructure.corpus_diff_payload import CorpusDiffPayload
from slice_runner.infrastructure.corpus_verdict_payload import CorpusVerdictPayload
from slice_runner.infrastructure.durable_ledger import DurableLedger, ReadableDurableLedger

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class LocalCorpus(Corpus):
    LEDGER: ClassVar[str] = "verdicts"
    DIFF_LEDGER: ClassVar[str] = "diffs"

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._verdicts: ReadableDurableLedger[CorpusVerdictPayload] = ReadableDurableLedger(
            name=self.LEDGER, row=CorpusVerdictPayload
        )
        self._diffs: DurableLedger[CorpusDiffPayload] = DurableLedger(name=self.DIFF_LEDGER, row=CorpusDiffPayload)

    def record(self, entry: CorpusEntry) -> None:
        ts = self._clock.now().isoformat()
        self._verdicts.append(CorpusVerdictPayload.from_domain(entry, ts=ts))
        self._diffs.append(CorpusDiffPayload.from_domain(entry, ts=ts))

    def size_of_the_last_verification(self, coordinates: SliceCoordinates) -> DiffStats | None:
        latest = self._verdicts.last_row_where(lambda data: CorpusVerdictPayload.may_belong_to(data, coordinates))

        return latest.diff_stats.to_domain() if latest is not None else None

    def fingerprint_of_the_last_verification(self, coordinates: SliceCoordinates) -> str | None:
        latest = self._verdicts.last_row_where(lambda data: CorpusVerdictPayload.may_belong_to(data, coordinates))

        return latest.diff_fingerprint if latest is not None else None

    def rounds_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[JudgedRound, ...]:
        last_row_of: dict[int, CorpusVerdictPayload] = {}
        for row in self._verdicts.rows_where(lambda data: CorpusVerdictPayload.may_belong_to(data, coordinates)):
            last_row_of[row.verify_round] = row

        return tuple(
            JudgedRound(round=verify_round, findings=tuple(finding.to_domain() for finding in row.verdict.findings))
            for verify_round, row in sorted(last_row_of.items())
        )
