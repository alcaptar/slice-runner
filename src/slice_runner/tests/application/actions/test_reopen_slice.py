from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.reopen_slice import ReopenSlice, ReopenSliceParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.exceptions import ImpossibleTransitionError, OrderRefusedError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.order import Order
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/slice-runner"
_INSTRUCTION = "el control ya esta arreglado a mano"

_BLOCKS: list[tuple[IssueLabel, Run, Run]] = [
    (
        IssueLabel.BLOCKED_CONTROLS,
        replace(RunMother.blocked_on_controls(), control_retries=2, hygiene_retries=2),
        replace(RunMother.blocked_on_controls(), step=Step.IMPLEMENT, control_retries=0, hygiene_retries=0),
    ),
    (
        IssueLabel.BLOCKED_JUDGE,
        RunMother.blocked_on_verify(),
        replace(RunMother.blocked_on_verify(), verify_retries=0),
    ),
    (IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci(), replace(RunMother.blocked_on_red_ci(), ci_retries=0)),
    (
        IssueLabel.BLOCKED_CI_INDETERMINATE,
        RunMother.blocked_on_indeterminate_ci(),
        replace(RunMother.blocked_on_indeterminate_ci(), indeterminate_ticks=0),
    ),
    (
        IssueLabel.BLOCKED_CI_CONFLICT,
        RunMother.blocked_on_conflict(),
        replace(RunMother.blocked_on_conflict(), catch_up_retries=0),
    ),
    (IssueLabel.BLOCKED_WORKTREE, RunMother.blocked_on_the_worktree(), RunMother.blocked_on_the_worktree()),
    (
        IssueLabel.BLOCKED_WORKTREE,
        replace(RunMother.blocked_on_the_worktree(), tree_unexpected=True),
        replace(RunMother.blocked_on_the_worktree(), tree_unexpected=True),
    ),
    (
        IssueLabel.ABORTED_BUDGET,
        RunMother.aborted_for_budget(HarnessSpendMother.of_the_implementer_call()),
        replace(
            RunMother.aborted_for_budget(HarnessSpendMother.of_the_implementer_call()), spend=HarnessSpend.nothing()
        ),
    ),
    (
        IssueLabel.ABORTED_UNMEASURED_CALL,
        RunMother.aborted_for_an_unmeasured_call(HarnessSpendMother.of_the_implementer_call()),
        RunMother.aborted_for_an_unmeasured_call(HarnessSpendMother.of_the_implementer_call()),
    ),
]


class TestReopenSlice:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)

        return repository

    @pytest.fixture
    def action(self, repository: Mock) -> ReopenSlice:
        return ReopenSlice(repository=repository, machine=StateMachine(budgets=Budgets()))

    @pytest.mark.parametrize(("label", "blocked_run", "reopened_run"), _BLOCKS)
    def test_the_budget_that_closed_the_run_is_the_only_one_restored(
        self, action: ReopenSlice, repository: Mock, label: IssueLabel, blocked_run: Run, reopened_run: Run
    ) -> None:
        subissue = SubIssueMother.blocked(label, blocked_run)

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO, issue=subissue.number, run=replace(reopened_run, retry_instruction=_INSTRUCTION)
        )

    @pytest.mark.parametrize(("label", "blocked_run", "reopened_run"), _BLOCKS)
    def test_the_blocking_label_is_swapped_for_the_one_that_matches_the_resumed_step(
        self, action: ReopenSlice, repository: Mock, label: IssueLabel, blocked_run: Run, reopened_run: Run
    ) -> None:
        subissue = SubIssueMother.blocked(label, blocked_run)

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_label.assert_called_once_with(
            repo=_REPO, issue=subissue.number, remove=label, add=IssueLabel.IN_PROGRESS
        )

    def test_reopening_after_a_conflict_also_resets_the_indeterminate_ticks_piled_up_before_it(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(
            IssueLabel.BLOCKED_CI_CONFLICT, RunMother.blocked_on_conflict_with_indeterminate_ticks_piled_up()
        )

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO,
            issue=subissue.number,
            run=replace(
                RunMother.blocked_on_conflict_with_indeterminate_ticks_piled_up(),
                catch_up_retries=0,
                indeterminate_ticks=0,
                retry_instruction=_INSTRUCTION,
            ),
        )

    def test_a_run_blocked_on_controls_while_catching_up_the_branch_is_reopened_no_longer_catching_it_up(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(
            IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls_while_catching_up_the_branch()
        )

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        assert repository.write_run.call_args.kwargs["run"].catching_up_the_branch is False

    def test_the_order_that_reopened_the_slice_is_left_on_the_subissue_with_its_instruction(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.mark_order.assert_called_once_with(
            repo=_REPO, issue=subissue.number, order=Order.RETRY, text=_INSTRUCTION
        )

    def test_the_result_carries_the_reopened_subissue_and_the_instruction_that_reopened_it(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        result = action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        assert result.subissue == replace(
            subissue,
            run=replace(
                RunMother.blocked_on_controls(), step=Step.IMPLEMENT, control_retries=0, retry_instruction=_INSTRUCTION
            ),
            label=IssueLabel.IN_PROGRESS,
        )
        assert result.instruction == _INSTRUCTION

    def test_a_subissue_with_no_run_on_record_cannot_be_reopened(self, action: ReopenSlice) -> None:
        subissue = replace(
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()), run=None
        )

        with pytest.raises(ImpossibleTransitionError, match=str(subissue.number)):
            action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

    def test_a_subissue_carrying_no_label_cannot_be_reopened(self, action: ReopenSlice) -> None:
        subissue = replace(
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()), label=None
        )

        with pytest.raises(ImpossibleTransitionError, match=str(subissue.number)):
            action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

    def test_a_run_aborted_before_touching_code_is_reopened_not_expecting_the_tree_it_could_not_retire(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        aborted = SubIssueMother.blocked(IssueLabel.ABORTED_BUDGET, RunMother.aborted_before_touching_code())

        action.execute(ReopenSliceParams(repo=_REPO, subissue=aborted, instruction=_INSTRUCTION))

        assert repository.write_run.call_args.kwargs["run"].tree_unexpected is True

    def test_a_run_blocked_while_it_kept_its_tree_is_reopened_expecting_it(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_JUDGE, RunMother.blocked_on_verify())

        action.execute(ReopenSliceParams(repo=_REPO, subissue=blocked, instruction=_INSTRUCTION))

        assert repository.write_run.call_args.kwargs["run"].tree_unexpected is False

    @pytest.mark.parametrize(
        "subissue",
        [
            SubIssueMother.pending(),
            replace(SubIssueMother.pending(), label=IssueLabel.IN_PROGRESS, run=RunMother.implementing()),
        ],
    )
    def test_a_slice_that_is_neither_blocked_nor_aborted_is_refused_before_writing_anything(
        self, action: ReopenSlice, repository: Mock, subissue: SubIssue
    ) -> None:
        with pytest.raises(OrderRefusedError, match=str(subissue.number)):
            action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_not_called()
        repository.write_label.assert_not_called()
        repository.mark_order.assert_not_called()
