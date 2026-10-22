from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.implement_slice import ImplementSlice, ImplementSliceParams
from slice_runner.domain.debt_ledger import DebtLedger
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.workspace import Workspace
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.implementation import Implementation


class _Rounds:
    WORKTREE = "/worktree"

    def __init__(self, *, cites_a_design: bool) -> None:
        self._cites_a_design = cites_a_design
        clearing = ("rm", "-rf", "--", DesignCapturesDirectory.of(self.WORKTREE))
        self._process = AnsweringByArgv(*(Answer.to_exactly(*clearing),) * 2) if cites_a_design else AnsweringByArgv()
        self.cleared_when_each_round_started: list[int] = []
        implementer: Mock = create_autospec(Implementer, spec_set=True, instance=True)
        implementer.implement.side_effect = self._implementing
        self._action = ImplementSlice(
            implementer=implementer,
            reader=create_autospec(DiffReader, spec_set=True, instance=True),
            debt_ledger=create_autospec(DebtLedger, spec_set=True, instance=True),
            captures=ProcessDesignCaptureStore(process=self._process),
            workspace=create_autospec(Workspace, spec_set=True, instance=True),
        )

    def _implementing(self, assignment: Assignment) -> Implementation:
        self.cleared_when_each_round_started.append(self._process.times_invoked("rm"))

        return ImplementationMother.of_two_paths()

    def run_two(self) -> None:
        params = ImplementSliceParams(
            repo="alcaptar/slice-runner",
            worktree=self.WORKTREE,
            subissue=SubIssueMother.naming_designs("detalle") if self._cites_a_design else SubIssueMother.pending(),
            parent=ParentIssueMother.declaring_two_designs(),
        )
        self._action.execute(params)
        self._action.execute(params)


class TestWhatTheFirstRoundLeavesInTheCapturesDirectory:
    def test_the_directory_is_cleared_before_each_round_starts_so_round_two_does_not_find_the_first(self) -> None:
        rounds = _Rounds(cites_a_design=True)

        rounds.run_two()

        assert rounds.cleared_when_each_round_started == [1, 2]

    def test_a_slice_that_cites_no_design_keeps_what_is_in_the_directory(self) -> None:
        rounds = _Rounds(cites_a_design=False)

        rounds.run_two()

        assert rounds.cleared_when_each_round_started == [0, 0]
