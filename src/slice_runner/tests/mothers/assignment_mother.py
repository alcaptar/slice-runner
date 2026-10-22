from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.domain.assignment import Assignment
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother


class AssignmentMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    WORKTREE: ClassVar[str] = "/repos/slice-runner"
    PLAN_PIECE: ClassVar[str] = (
        "SubissueAlreadyClosedPrecheck.blocking(subissue): comprueba el precheck de subissue cerrada antes de "
        "tocar la rama."
    )
    DECISIONS: ClassVar[tuple[str, ...]] = (
        "el padre decide que la regla vive en el dominio",
        "el padre decide que el adaptador no captura el OSError",
        "la subissue decide que el campo se llama decisions",
        "la subissue decide que la tupla vacia no emite seccion",
    )
    RETRY_INSTRUCTION: ClassVar[str] = "el control ya esta arreglado a mano"
    REVIEW: ClassVar[str] = "falta manejar el caso donde la lista viene vacia"

    @classmethod
    def of_the_first_round(cls) -> Assignment:
        subissue = SubIssueMother.pending()
        parent = ParentIssueMother.with_sources_and_controls()

        return Assignment(
            issue=subissue.number,
            slice_id=subissue.slice_id.canonical,
            repo=cls.REPO,
            worktree=cls.WORKTREE,
            intention=subissue.intention,
            prior_art="",
            criteria=subissue.criteria,
            signal=subissue.signal,
            excludes=subissue.excludes,
            replaces=subissue.replaces,
            sources=parent.sources,
            controls=parent.controls,
        )

    @classmethod
    def of_the_first_round_of_a_slice_with_a_user_story(cls) -> Assignment:
        return replace(cls.of_the_first_round(), slice_id=SubIssueMother.carrying_a_user_story().slice_id.canonical)

    @classmethod
    def of_a_slice_that_excludes_something(cls) -> Assignment:
        return replace(cls.of_the_first_round(), excludes="el panel de grafana que consume esta serie")

    @classmethod
    def of_a_slice_that_replaces_something(cls) -> Assignment:
        return replace(cls.of_the_first_round(), replaces="si - el adaptador viejo; apagando el flag")

    @classmethod
    def of_a_second_round(cls) -> Assignment:
        return replace(cls.of_the_first_round(), findings=(FindingMother.with_line(),))

    @classmethod
    def of_a_round_after_red_controls(cls) -> Assignment:
        return replace(cls.of_the_first_round(), control_logs=(ControlOutcomeMother.LOG,))

    @classmethod
    def of_a_round_after_a_dirty_index(cls) -> Assignment:
        return replace(
            cls.of_the_first_round(),
            hygiene_refusal="the staged index is not what the implementer reported: src/leftover.py (not-declared)",
        )

    @classmethod
    def of_a_round_after_a_dead_call(cls) -> Assignment:
        return replace(cls.of_the_first_round(), dirty_worktree_files=("src/leftover.py", "src/removed.py"))

    @classmethod
    def of_a_round_after_a_retry_with_staged_files(cls) -> Assignment:
        return replace(cls.of_the_first_round(), staged_files=("src/kept.py", "src/tests/test_kept.py"))

    @classmethod
    def of_a_repo_exempt_from_controls(cls) -> Assignment:
        return replace(cls.of_the_first_round(), controls=ParentIssueMother.with_exempt_controls().controls)

    @classmethod
    def of_the_first_round_with_decisions(cls) -> Assignment:
        return replace(cls.of_the_first_round(), decisions=cls.DECISIONS)

    @classmethod
    def of_a_round_after_reopening(cls) -> Assignment:
        return replace(cls.of_the_first_round(), retry_instruction=cls.RETRY_INSTRUCTION)

    @classmethod
    def of_a_round_after_reopening_and_a_review(cls) -> Assignment:
        return replace(cls.of_a_round_after_reopening(), requested_changes=(RequestedChange(body=cls.REVIEW),))

    @classmethod
    def of_a_round_after_a_review(cls) -> Assignment:
        return replace(cls.of_the_first_round(), requested_changes=(RequestedChange(body=cls.REVIEW),))

    @classmethod
    def of_a_round_after_a_review_with_an_anchored_comment(cls) -> Assignment:
        return replace(
            cls.of_the_first_round(),
            requested_changes=(
                RequestedChange(body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(),)),
            ),
        )

    @classmethod
    def of_a_round_after_a_review_with_a_body_and_an_anchored_comment(cls) -> Assignment:
        return replace(
            cls.of_the_first_round(),
            requested_changes=(
                RequestedChange(body=cls.REVIEW, comments=(PullRequestReviewCommentMother.anchored_to_a_line(),)),
            ),
        )

    @classmethod
    def of_a_round_after_a_stale_review_comment(cls) -> Assignment:
        return replace(
            cls.of_the_first_round(),
            requested_changes=(
                RequestedChange(
                    body="", comments=(PullRequestReviewCommentMother.without_a_line_because_it_went_stale(),)
                ),
            ),
        )

    @classmethod
    def of_a_slice_with_the_board_design(cls) -> Assignment:
        return replace(cls.of_the_first_round(), designs=(DesignMother.board(),))

    @classmethod
    def of_a_slice_with_two_designs(cls) -> Assignment:
        return replace(cls.of_the_first_round(), designs=(DesignMother.board(), DesignMother.detail()))
