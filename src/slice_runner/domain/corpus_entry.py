from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_diff import SliceDiff
    from slice_runner.domain.verdict import Verdict


@dataclass(frozen=True, kw_only=True, slots=True)
class CorpusEntry:
    repo: str
    issue: int
    slice_id: str
    verify_round: int
    session: str
    diff: SliceDiff
    verdict: Verdict
    prior_findings_given: int
