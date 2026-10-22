from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.corpus_entry import CorpusEntry
from slice_runner.tests.mothers.verdict_mother import VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother

if TYPE_CHECKING:
    from slice_runner.domain.slice_diff import SliceDiff
    from slice_runner.domain.verdict import Verdict


class CorpusEntryMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 11
    SLICE_ID: ClassVar[str] = "slice-11"
    VERIFY_ROUND: ClassVar[int] = 1
    SESSION: ClassVar[str] = "e3f6a3d0-1c8a-4a7b-9c2e-5f6a7b8c9d0e"
    PRIOR_FINDINGS_GIVEN: ClassVar[int] = 0

    @classmethod
    def of_the_slice(
        cls,
        *,
        repo: str | None = None,
        issue: int | None = None,
        slice_id: str | None = None,
        verify_round: int | None = None,
        session: str | None = None,
        verdict: Verdict | None = None,
        diff: SliceDiff | None = None,
        prior_findings_given: int | None = None,
    ) -> CorpusEntry:
        return CorpusEntry(
            repo=repo or cls.REPO,
            issue=cls.ISSUE if issue is None else issue,
            slice_id=slice_id or cls.SLICE_ID,
            verify_round=cls.VERIFY_ROUND if verify_round is None else verify_round,
            session=session or cls.SESSION,
            diff=diff or SliceDiffMother.of_the_slice(),
            verdict=verdict or VerdictMother.passing(),
            prior_findings_given=cls.PRIOR_FINDINGS_GIVEN if prior_findings_given is None else prior_findings_given,
        )
