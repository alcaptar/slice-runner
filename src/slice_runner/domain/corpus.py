from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.slice_coordinates import SliceCoordinates


@dataclass(frozen=True, kw_only=True, slots=True)
class JudgedRound:
    round: int
    findings: tuple[Finding, ...]


class Corpus(ABC):
    @abstractmethod
    def record(self, entry: CorpusEntry) -> None: ...

    @abstractmethod
    def size_of_the_last_verification(self, coordinates: SliceCoordinates) -> DiffStats | None: ...

    @abstractmethod
    def fingerprint_of_the_last_verification(self, coordinates: SliceCoordinates) -> str | None: ...

    @abstractmethod
    def rounds_of_the_slice(self, coordinates: SliceCoordinates) -> tuple[JudgedRound, ...]: ...
