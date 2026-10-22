from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.application.actions.verify_slice import VerifySliceParams
from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.judge import Judge
from slice_runner.domain.slice_diff import SliceDiff
from slice_runner.domain.slice_under_review import SliceUnderReview
from slice_runner.domain.verification import Verification
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.domain.design_captures import DesignCaptures
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures
    from slice_runner.domain.source import Source
    from slice_runner.domain.verdict import Verdict


class SliceDiffMother:
    TOUCHED: ClassVar[tuple[str, ...]] = ("src/mod.py", "src/tests/test_mod.py")
    TEXT: ClassVar[str] = (
        "diff --git a/src/mod.py b/src/mod.py\n"
        "--- a/src/mod.py\n"
        "+++ b/src/mod.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-    return 1\n"
        "+    return 2\n"
    )
    STATS: ClassVar[DiffStats] = DiffStats(files_changed=2, lines_added=1, lines_deleted=1)

    @classmethod
    def of_the_slice(
        cls, *, files: tuple[str, ...] | None = None, text: str | None = None, stats: DiffStats | None = None
    ) -> SliceDiff:
        return SliceDiff(
            text=text if text is not None else cls.TEXT, files=files or cls.TOUCHED, stats=stats or cls.STATS
        )


class VerifySliceParamsMother:
    BASE: ClassVar[str] = "master"

    @classmethod
    def against_the_base(cls) -> VerifySliceParams:
        return VerifySliceParams(
            repo=SliceUnderReviewMother.REPO,
            issue=SliceUnderReviewMother.ISSUE,
            worktree=SliceUnderReviewMother.WORKTREE,
            base=cls.BASE,
            slice_id=SliceUnderReviewMother.SLICE_ID,
            verify_round=1,
            signal=SliceUnderReviewMother.signal(),
            excludes=SliceUnderReviewMother.excludes(),
            replaces=SliceUnderReviewMother.replaces(),
            prior_art="",
            criteria=SliceUnderReviewMother.criteria(),
            sources=SliceUnderReviewMother.sources(),
            checklist=SliceUnderReviewMother.checklist(),
            prior_findings=(),
            debt=(),
            decisions=(),
            deviations=(),
            designs=(),
            captures=DesignCapturesMother.none(),
            compares_with_the_last_verification=False,
        )


class SliceUnderReviewMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 45
    WORKTREE: ClassVar[str] = "/repos/project"
    SLICE_ID: ClassVar[str] = "slice-05"
    SLICE_ID_WITH_A_USER_STORY: ClassVar[str] = "PROJ-1234-05"

    @classmethod
    def of_the_slice(
        cls,
        *,
        worktree: str | None = None,
        files: tuple[str, ...] | None = None,
        text: str | None = None,
        slice_id: str | None = None,
        excludes: str | None = None,
        replaces: str | None = None,
        prior_findings: tuple[Finding, ...] | None = None,
        debt: tuple[str, ...] | None = None,
        decisions: tuple[str, ...] | None = None,
        deviations: tuple[str, ...] | None = None,
        designs: tuple[Design, ...] | None = None,
        captures: DesignCaptures | MissingDesignCaptures | None = None,
    ) -> SliceUnderReview:
        return SliceUnderReview(
            slice_id=slice_id or cls.SLICE_ID,
            repo=cls.REPO,
            issue=cls.ISSUE,
            worktree=worktree or cls.WORKTREE,
            diff=SliceDiffMother.of_the_slice(files=files, text=text),
            signal=cls.signal(),
            excludes=excludes if excludes is not None else cls.excludes(),
            replaces=replaces if replaces is not None else cls.replaces(),
            prior_art="",
            criteria=cls.criteria(),
            sources=cls.sources(),
            checklist=cls.checklist(),
            prior_findings=prior_findings if prior_findings is not None else (),
            debt=debt if debt is not None else (),
            decisions=decisions if decisions is not None else (),
            deviations=deviations if deviations is not None else (),
            designs=designs if designs is not None else (),
            captures=captures if captures is not None else DesignCapturesMother.none(),
        )

    @staticmethod
    def signal() -> str:
        return SubIssueMother.pending().signal

    @staticmethod
    def excludes() -> str:
        return SubIssueMother.pending().excludes

    @staticmethod
    def replaces() -> str:
        return SubIssueMother.pending().replaces

    @staticmethod
    def criteria() -> tuple[str, ...]:
        return SubIssueMother.pending().criteria

    @staticmethod
    def sources() -> tuple[Source, ...]:
        return ParentIssueMother.with_sources_and_controls().sources

    @staticmethod
    def checklist() -> tuple[ChecklistEntry, ...]:
        return (ChecklistEntry.of(SubIssueMother.closed()), ChecklistEntry.of(SubIssueMother.of_another_repo()))

    @staticmethod
    def two_declared_gaps() -> tuple[str, ...]:
        return ("el cableado del subcomando queda para otra slice", "la migracion de datos historicos")

    @staticmethod
    def one_decision_of_the_parent_and_one_of_the_subissue() -> tuple[str, ...]:
        return (
            "el padre decide el reparto de responsabilidades entre las capas",
            "la subissue decide que el campo se llama deviations",
        )

    @staticmethod
    def two_declared_deviations() -> tuple[str, ...]:
        return (
            "el puerto no admite la firma decidida porque ya la consume otro adaptador",
            "la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza",
        )


class JudgeMother:
    RUBRIC: ClassVar[str] = "You are the adversarial verifier."
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill")
    YARDSTICK: ClassVar[Path] = Path("/toolbox/skills")

    @classmethod
    def adversarial(cls) -> Judge:
        return Judge(rubric=cls.RUBRIC, tools=cls.TOOLS)

    @classmethod
    def reading_the_repo_and_its_yardstick(cls) -> Judge:
        return cls.adversarial().also_reading(Path(SliceUnderReviewMother.WORKTREE), cls.YARDSTICK)


class VerificationMother:
    DENIED_READ: ClassVar[str] = "Read /toolbox/skills/x.md"
    SESSION: ClassVar[str] = "e3f6a3d0-1c8a-4a7b-9c2e-5f6a7b8c9d0e"

    @classmethod
    def passing(cls) -> Verification:
        return Verification(
            verdict=VerdictMother.passing(),
            spend=HarnessSpendMother.of_the_judge_call(),
            session=cls.SESSION,
        )

    @classmethod
    def vetoing(cls, verdict: Verdict) -> Verification:
        return Verification(
            verdict=verdict,
            spend=HarnessSpendMother.of_the_judge_call(),
            session=cls.SESSION,
        )

    @classmethod
    def approving_with_accepted_debt(cls, *findings: Finding) -> Verification:
        chosen = findings or (FindingMother.low_severity(),)

        return Verification(
            verdict=VerdictMother.passing_with(*chosen),
            spend=HarnessSpendMother.of_the_judge_call(),
            session=cls.SESSION,
        )

    @classmethod
    def failing_after_a_denied_read(cls) -> Verification:
        return Verification(
            verdict=VerdictMother.failing(),
            spend=HarnessSpendMother.of_the_judge_call(),
            session=cls.SESSION,
            denied_reads=(cls.DENIED_READ,),
        )
