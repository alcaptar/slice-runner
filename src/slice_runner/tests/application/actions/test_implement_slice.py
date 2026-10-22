from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.implement_slice import ImplementSlice, ImplementSliceParams
from slice_runner.domain.debt_ledger import DebtLedger
from slice_runner.domain.design_capture_store import DesignCaptureStore
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.workspace import Workspace
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/slice-runner"
_WORKTREE = "/repos/slice-runner"


class TestImplementSlice:
    @pytest.fixture
    def implementer(self) -> Mock:
        implementer: Mock = create_autospec(Implementer, spec_set=True, instance=True)
        implementer.implement.return_value = ImplementationMother.of_two_paths()
        return implementer

    @pytest.fixture
    def reader(self) -> Mock:
        reader: Mock = create_autospec(DiffReader, spec_set=True, instance=True)
        reader.dirty.return_value = ()
        return reader

    @pytest.fixture
    def debt_ledger(self) -> Mock:
        debt_ledger: Mock = create_autospec(DebtLedger, spec_set=True, instance=True)
        return debt_ledger

    @pytest.fixture
    def captures(self) -> Mock:
        captures: Mock = create_autospec(DesignCaptureStore, spec_set=True, instance=True)
        return captures

    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.staged.return_value = ()
        return workspace

    @pytest.fixture
    def action(
        self, implementer: Mock, reader: Mock, debt_ledger: Mock, captures: Mock, workspace: Mock
    ) -> ImplementSlice:
        return ImplementSlice(
            implementer=implementer, reader=reader, debt_ledger=debt_ledger, captures=captures, workspace=workspace
        )

    @staticmethod
    def _params(
        *findings: Finding, subissue: SubIssue | None = None, previous_call_died: bool = False
    ) -> ImplementSliceParams:
        return ImplementSliceParams(
            repo=_REPO,
            worktree=_WORKTREE,
            subissue=subissue or SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            findings=findings,
            previous_call_died=previous_call_died,
        )

    @staticmethod
    def _assigned(implementer: Mock) -> Assignment:
        assignment: Assignment = implementer.implement.call_args.args[0]
        return assignment

    def test_the_assignment_names_the_slice_and_the_issue_it_belongs_to(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assigned = self._assigned(implementer)
        assert (assigned.issue, assigned.slice_id) == (SubIssueMother.pending().number, "slice-05")

    def test_a_slice_carrying_a_user_story_is_assigned_by_its_canonical_identifier_not_the_bare_ordinal(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params(subissue=SubIssueMother.carrying_a_user_story()))

        assert self._assigned(implementer).slice_id == "PROJ-1234-05"

    def test_what_the_slice_asks_for_travels_from_the_body_of_its_own_subissue(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        subissue = SubIssueMother.pending()
        assigned = self._assigned(implementer)
        assert (assigned.intention, assigned.criteria, assigned.signal) == (
            subissue.intention,
            subissue.criteria,
            subissue.signal,
        )

    def test_what_the_slice_declares_as_excluded_travels_to_the_assignment_too(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        subissue = SubIssueMother.declaring_an_exclusion()

        action.execute(self._params(subissue=subissue))

        assert self._assigned(implementer).excludes == subissue.excludes

    def test_what_the_slice_declares_it_replaces_travels_to_the_assignment_too(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        subissue = SubIssueMother.declaring_a_replacement()

        action.execute(self._params(subissue=subissue))

        assert self._assigned(implementer).replaces == subissue.replaces

    def test_the_yardstick_and_the_controls_come_from_the_parent_because_the_slice_declares_neither(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        parent = ParentIssueMother.with_sources_and_controls()
        assigned = self._assigned(implementer)
        assert (assigned.sources, assigned.controls) == (parent.sources, parent.controls)

    def test_the_worktree_that_is_assigned_is_where_the_work_happens(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).worktree == _WORKTREE

    def test_the_repo_that_is_assigned_is_the_real_repo_of_the_issue_and_not_the_worktree(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).repo == _REPO

    def test_a_first_round_assigns_no_findings_at_all(self, action: ImplementSlice, implementer: Mock) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).findings == ()

    def test_a_second_round_assigns_the_findings_the_verifier_raised_so_the_retry_knows_what_to_fix(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        raised = FindingMother.with_line()

        action.execute(self._params(raised))

        assert self._assigned(implementer).findings == (raised,)

    def test_the_implementation_comes_back_without_being_reinterpreted(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        assert action.execute(self._params()) == ImplementationMother.of_two_paths()

    def test_the_log_of_a_control_in_red_is_assigned_as_a_path_because_nobody_who_judges_reads_build_output(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), control_logs=(ControlOutcomeMother.LOG,)))

        assert self._assigned(implementer).control_logs == (ControlOutcomeMother.LOG,)

    def test_the_refusal_of_a_dirty_index_is_assigned_because_otherwise_the_round_repeats_it_blind(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), hygiene_refusal="src/leftover.py (not-declared)"))

        assert self._assigned(implementer).hygiene_refusal == "src/leftover.py (not-declared)"

    def test_the_decisions_of_the_parent_come_before_those_of_the_subissue_in_the_assignment(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        parent = replace(ParentIssueMother.with_sources_and_controls(), decisions=("padre uno", "padre dos"))
        subissue = replace(SubIssueMother.pending(), decisions=("subissue uno", "subissue dos"))

        action.execute(replace(self._params(subissue=subissue), parent=parent))

        assert self._assigned(implementer).decisions == ("padre uno", "padre dos", "subissue uno", "subissue dos")

    def test_only_the_designs_the_subissue_names_travel_in_the_assignment(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        parent = ParentIssueMother.declaring_two_designs()
        subissue = SubIssueMother.naming_designs("detalle")

        action.execute(replace(self._params(subissue=subissue), parent=parent))

        assert self._assigned(implementer).designs == (DesignMother.detail(),)

    def test_a_subissue_that_names_no_design_assigns_none_though_the_parent_declares_some(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), parent=ParentIssueMother.declaring_two_designs()))

        assert self._assigned(implementer).designs == ()

    def test_a_slice_with_a_design_has_its_captures_cleared_before_the_implementer_starts(
        self, action: ImplementSlice, implementer: Mock, captures: Mock
    ) -> None:
        cleared_when_the_implementer_started: list[bool] = []

        def implementing(assignment: Assignment) -> object:
            cleared_when_the_implementer_started.append(captures.clear.called)
            return ImplementationMother.of_two_paths()

        implementer.implement.side_effect = implementing
        subissue = SubIssueMother.naming_designs("detalle")

        action.execute(replace(self._params(subissue=subissue), parent=ParentIssueMother.declaring_two_designs()))

        captures.clear.assert_called_once_with(worktree=_WORKTREE)
        assert cleared_when_the_implementer_started == [True]

    def test_a_slice_that_cites_no_design_leaves_the_captures_directory_alone(
        self, action: ImplementSlice, captures: Mock
    ) -> None:
        action.execute(replace(self._params(), parent=ParentIssueMother.declaring_two_designs()))

        captures.clear.assert_not_called()

    def test_a_previous_call_that_died_asks_the_reader_and_assigns_the_files_it_found_dirty(
        self, action: ImplementSlice, implementer: Mock, reader: Mock
    ) -> None:
        reader.dirty.return_value = ("src/leftover.py",)

        action.execute(self._params(previous_call_died=True))

        reader.dirty.assert_called_once_with(worktree=_WORKTREE)
        assert self._assigned(implementer).dirty_worktree_files == ("src/leftover.py",)

    def test_a_round_that_did_not_follow_a_dead_call_never_asks_the_reader_and_assigns_no_file(
        self, action: ImplementSlice, implementer: Mock, reader: Mock
    ) -> None:
        action.execute(self._params(previous_call_died=False))

        reader.dirty.assert_not_called()
        assert self._assigned(implementer).dirty_worktree_files == ()

    def test_a_retry_assigns_the_files_already_in_the_index_so_the_implementer_declares_them_again(
        self, action: ImplementSlice, implementer: Mock, workspace: Mock
    ) -> None:
        workspace.staged.return_value = ("src/kept.py", "src/tests/test_kept.py")

        action.execute(replace(self._params(), retry_instruction="el control ya esta arreglado a mano"))

        workspace.staged.assert_called_once_with(worktree=_WORKTREE)
        assert self._assigned(implementer).staged_files == ("src/kept.py", "src/tests/test_kept.py")

    def test_a_round_without_a_retry_instruction_assigns_no_staged_file_though_the_index_has_some(
        self, action: ImplementSlice, implementer: Mock, workspace: Mock
    ) -> None:
        workspace.staged.return_value = ("src/kept.py", "src/tests/test_kept.py")

        action.execute(self._params())

        assert self._assigned(implementer).staged_files == ()

    def test_what_the_implementer_declares_left_out_is_written_to_the_ledger_in_the_same_call(
        self, action: ImplementSlice, implementer: Mock, debt_ledger: Mock
    ) -> None:
        implementer.implement.return_value = ImplementationMother.with_debt()

        action.execute(self._params())

        recorded = debt_ledger.record.call_args.args[0]
        assert recorded.left_out == ImplementationMother.with_debt().left_out

    def test_the_declaration_is_written_with_the_coordinates_of_the_slice_being_implemented(
        self, action: ImplementSlice, debt_ledger: Mock
    ) -> None:
        action.execute(self._params(subissue=SubIssueMother.pending()))

        recorded = debt_ledger.record.call_args.args[0]
        subissue = SubIssueMother.pending()
        assert (recorded.coordinates.repo, recorded.coordinates.issue, recorded.coordinates.slice_id) == (
            _REPO,
            subissue.number,
            subissue.slice_id.canonical_id,
        )

    def test_the_deviations_the_implementer_declares_never_reach_the_ledger(
        self, action: ImplementSlice, implementer: Mock, debt_ledger: Mock
    ) -> None:
        implementer.implement.return_value = ImplementationMother.with_two_deviations()

        action.execute(self._params())

        recorded = debt_ledger.record.call_args.args[0]
        assert recorded.left_out == ()

    def test_an_empty_left_out_list_is_still_written_instead_of_staying_silent(
        self, action: ImplementSlice, debt_ledger: Mock
    ) -> None:
        action.execute(self._params())

        recorded = debt_ledger.record.call_args.args[0]
        assert recorded.left_out == ()
