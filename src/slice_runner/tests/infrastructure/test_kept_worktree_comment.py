from __future__ import annotations

import pytest

from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.kept_worktree_comment import KeptWorktreeComment

_PATH = "/repos/slice-runner/.worktrees/05-prechecks-deterministas"

_WHAT_EACH_KEPT_WORKTREE_SAYS = {
    WorktreeRetirement.KEPT_UNCOMMITTED_WORK: "cambios sin comitear",
    WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS: "commits que solo existen en local",
    WorktreeRetirement.KEPT_UNVERIFIABLE: "no se pudo comprobar",
    WorktreeRetirement.KEPT_REMOVAL_FAILED: "git no pudo retirarlo",
    WorktreeRetirement.KEPT_FOR_RESUMING: "para reanudar",
    WorktreeRetirement.KEPT_UNEXPECTED: "no se esperaba",
}


class TestKeptWorktreeComment:
    @pytest.mark.parametrize("retirement", list(_WHAT_EACH_KEPT_WORKTREE_SAYS))
    def test_every_kept_worktree_is_told_with_its_path_and_the_reason_it_stayed(
        self, retirement: WorktreeRetirement
    ) -> None:
        body = KeptWorktreeComment.rendered(path=_PATH, retirement=retirement)

        assert f"`{_PATH}`" in body
        assert _WHAT_EACH_KEPT_WORKTREE_SAYS[retirement] in body

    def test_the_reasons_are_told_apart_so_the_two_conditions_are_never_reported_as_one(self) -> None:
        bodies = {
            retirement: KeptWorktreeComment.rendered(path=_PATH, retirement=retirement)
            for retirement in _WHAT_EACH_KEPT_WORKTREE_SAYS
        }

        assert len(set(bodies.values())) == len(_WHAT_EACH_KEPT_WORKTREE_SAYS)

    def test_a_tree_found_where_none_was_expected_says_how_to_resolve_it_by_hand_with_the_command(self) -> None:
        body = KeptWorktreeComment.rendered(path=_PATH, retirement=WorktreeRetirement.KEPT_UNEXPECTED)

        assert f"git worktree remove {_PATH}" in body

    @pytest.mark.parametrize(
        "retirement",
        [
            retirement
            for retirement in WorktreeRetirement
            if retirement.kept and retirement is not WorktreeRetirement.KEPT_UNEXPECTED
        ],
    )
    def test_only_the_leftover_asks_a_person_to_resolve_anything_by_hand(self, retirement: WorktreeRetirement) -> None:
        assert "git worktree remove" not in KeptWorktreeComment.rendered(path=_PATH, retirement=retirement)

    def test_the_comment_is_marked_as_automatic(self) -> None:
        body = KeptWorktreeComment.rendered(path=_PATH, retirement=WorktreeRetirement.KEPT_FOR_RESUMING)

        assert body.endswith(AutomationMark.TEXT)

    @pytest.mark.parametrize("retirement", [WorktreeRetirement.RETIRED, WorktreeRetirement.NOT_MOUNTED])
    def test_a_worktree_that_is_not_kept_has_nothing_to_tell(self, retirement: WorktreeRetirement) -> None:
        with pytest.raises(ImpossibleTransitionError):
            KeptWorktreeComment.rendered(path=_PATH, retirement=retirement)
