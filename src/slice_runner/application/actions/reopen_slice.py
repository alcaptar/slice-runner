from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.closure import Closure
from slice_runner.domain.exceptions import ImpossibleTransitionError, OrderRefusedError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.order import Order
from slice_runner.domain.slice_queue import SliceQueue
from slice_runner.domain.worktree_retirement_policy import WorktreeRetirementPolicy

if TYPE_CHECKING:
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.state_machine import StateMachine
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ReopenSliceParams:
    repo: str
    subissue: SubIssue
    instruction: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ReopenSliceResult:
    subissue: SubIssue
    instruction: str


class ReopenSlice:
    def __init__(self, *, repository: RunRepository, machine: StateMachine) -> None:
        self._repository = repository
        self._machine = machine

    def execute(self, params: ReopenSliceParams) -> ReopenSliceResult:
        subissue = params.subissue
        if subissue.label is not None and not SliceQueue.blocked(subissue):
            raise OrderRefusedError(
                f"subissue #{subissue.number} is neither blocked nor aborted, so there is nothing to retry"
            )
        if subissue.run is None or subissue.label is None:
            raise ImpossibleTransitionError(
                f"subissue #{subissue.number} cannot be reopened without a closed run and a blocking label"
            )

        run = replace(
            self._machine.reopened(subissue.run, blocked=subissue.label),
            retry_instruction=params.instruction,
            tree_unexpected=not WorktreeRetirementPolicy.expects_a_tree(label=subissue.label, run=subissue.run),
        )
        label = IssueLabel.of(closure=Closure.open(), step=run.step)
        if label is None:
            raise ImpossibleTransitionError(f"the step `{run.step}` of an open run maps to no label")

        self._repository.write_run(repo=params.repo, issue=subissue.number, run=run)
        self._repository.write_label(repo=params.repo, issue=subissue.number, remove=subissue.label, add=label)
        self._repository.mark_order(repo=params.repo, issue=subissue.number, order=Order.RETRY, text=params.instruction)

        return ReopenSliceResult(subissue=replace(subissue, run=run, label=label), instruction=params.instruction)
