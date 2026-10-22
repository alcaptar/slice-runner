from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import Mock, call, create_autospec

import pytest

from slice_runner.application.actions.stage_slice import StageSlice, StageSliceParams
from slice_runner.domain.exceptions import DirtyIndexError
from slice_runner.domain.workspace import Workspace
from slice_runner.tests.mothers.reported_path_mother import ReportedPathMother

if TYPE_CHECKING:
    from slice_runner.domain.reported_path import ReportedPath

_WORKTREE = "/repos/slice-runner"
_UNDECLARED = "Makefile"


class TestStageSlice:
    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.staged.return_value = ()
        return workspace

    @pytest.fixture
    def action(self, workspace: Mock) -> StageSlice:
        return StageSlice(workspace=workspace)

    @staticmethod
    def _params(*paths: ReportedPath) -> StageSliceParams:
        return StageSliceParams(worktree=_WORKTREE, paths=paths)

    def test_every_declared_path_is_staged_whatever_its_kind(self, action: StageSlice, workspace: Mock) -> None:
        production = ReportedPathMother.production_file()
        test = ReportedPathMother.test_file()
        workspace.staged.return_value = (production.path, test.path)

        action.execute(self._params(production, test))

        workspace.stage.assert_called_once_with(worktree=_WORKTREE, paths=(production.path, test.path))

    def test_the_index_is_read_after_staging_so_the_check_sees_what_the_commit_would_carry(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        production = ReportedPathMother.production_file()
        workspace.staged.return_value = (production.path,)

        action.execute(self._params(production))

        assert workspace.mock_calls == [
            call.stage(worktree=_WORKTREE, paths=(production.path,)),
            call.staged(worktree=_WORKTREE),
        ]

    def test_an_index_that_carries_exactly_what_was_declared_goes_through(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        production = ReportedPathMother.production_file()
        test = ReportedPathMother.test_file()
        workspace.staged.return_value = (test.path, production.path)

        action.execute(self._params(production, test))

    def test_a_declared_plan_goes_through_like_any_other_declared_file(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        plan = ReportedPathMother.plan()
        workspace.staged.return_value = (plan.path,)

        action.execute(self._params(plan))

    def test_something_staged_outside_what_was_declared_blocks_and_names_the_path(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        production = ReportedPathMother.production_file()
        workspace.staged.return_value = (production.path, _UNDECLARED)

        with pytest.raises(DirtyIndexError, match=_UNDECLARED):
            action.execute(self._params(production))

    def test_declaring_nothing_blocks_whatever_is_staged_instead_of_letting_it_through(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        production = ReportedPathMother.production_file()
        workspace.staged.return_value = (production.path,)

        with pytest.raises(DirtyIndexError, match=re.escape(production.path)):
            action.execute(self._params())

    def test_a_declared_path_written_with_a_dot_segment_still_matches_the_index(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        workspace.staged.return_value = (ReportedPathMother.production_file().path,)

        action.execute(self._params(ReportedPathMother.production_file_with_a_dot_segment()))

    def test_a_blocked_index_is_left_staged_so_a_person_can_look_at_it(
        self, action: StageSlice, workspace: Mock
    ) -> None:
        production = ReportedPathMother.production_file()
        workspace.staged.return_value = (_UNDECLARED,)

        with pytest.raises(DirtyIndexError):
            action.execute(self._params(production))

        assert workspace.mock_calls == [
            call.stage(worktree=_WORKTREE, paths=(production.path,)),
            call.staged(worktree=_WORKTREE),
        ]
