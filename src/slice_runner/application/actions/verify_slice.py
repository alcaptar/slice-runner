from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.domain.exceptions import UnchangedDiffError
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.slice_under_review import SliceUnderReview

if TYPE_CHECKING:
    from slice_runner.domain.checklist_entry import ChecklistEntry
    from slice_runner.domain.corpus import Corpus
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.diff_reader import DiffReader
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.source import Source
    from slice_runner.domain.verification import Verification
    from slice_runner.domain.verifier import Verifier


@dataclass(frozen=True, kw_only=True, slots=True)
class VerifySliceParams:
    repo: str
    issue: int
    worktree: str
    base: str
    slice_id: str
    verify_round: int
    prior_art: str
    signal: str
    excludes: str
    replaces: str
    criteria: tuple[str, ...]
    sources: tuple[Source, ...]
    checklist: tuple[ChecklistEntry, ...]
    prior_findings: tuple[Finding, ...]
    debt: tuple[str, ...]
    decisions: tuple[str, ...]
    deviations: tuple[str, ...]
    designs: tuple[Design, ...]
    captures: DesignCaptures | MissingDesignCaptures
    compares_with_the_last_verification: bool


class VerifySlice:
    def __init__(
        self, *, reader: DiffReader, verifier: Verifier, judge: Judge, skills: SkillLibrary, corpus: Corpus
    ) -> None:
        self._reader = reader
        self._verifier = verifier
        self._judge = judge
        self._skills = skills
        self._corpus = corpus

    def execute(self, params: VerifySliceParams) -> Verification:
        diff = self._reader.read(worktree=params.worktree, base=params.base)
        if params.compares_with_the_last_verification and diff.repeats(self._last_fingerprint_of(params)):
            raise UnchangedDiffError(
                f"the diff of {params.slice_id} is identical to the one the judge already ruled on: "
                "the implementer left it untouched since"
            )

        verification = self._verifier.verify(
            self._judge_reading(params.worktree),
            SliceUnderReview(
                slice_id=params.slice_id,
                repo=params.repo,
                issue=params.issue,
                worktree=params.worktree,
                diff=diff,
                prior_art=params.prior_art,
                signal=params.signal,
                excludes=params.excludes,
                replaces=params.replaces,
                criteria=params.criteria,
                sources=params.sources,
                checklist=params.checklist,
                prior_findings=params.prior_findings,
                debt=params.debt,
                decisions=params.decisions,
                deviations=params.deviations,
                designs=params.designs,
                captures=params.captures,
            ),
        )
        self._corpus.record(
            CorpusEntry(
                repo=params.repo,
                issue=params.issue,
                slice_id=params.slice_id,
                verify_round=params.verify_round,
                session=verification.session,
                diff=diff,
                verdict=verification.verdict,
                prior_findings_given=len(params.prior_findings),
            )
        )

        return verification

    def _last_fingerprint_of(self, params: VerifySliceParams) -> str | None:
        return self._corpus.fingerprint_of_the_last_verification(
            SliceCoordinates(repo=params.repo, issue=params.issue, slice_id=CanonicalSliceId.of_text(params.slice_id))
        )

    def _judge_reading(self, worktree: str) -> Judge:
        return self._judge.also_reading(Path(worktree), *self._skills.directories())
