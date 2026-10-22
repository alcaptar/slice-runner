from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal, NoReturn

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.step import Step
from slice_runner.domain.transition import Transition

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class StateMachine:
    budgets: Budgets

    def after(
        self, run: Run, outcome: Outcome, *, call_died: bool = False, verdict_recorded: bool = False
    ) -> Transition:
        if outcome is Outcome.OVER_BUDGET:
            closing = self._marking_a_dead_call(run, call_died)
            if verdict_recorded:
                closing = self._logged_a_verify_round(closing)

            return self._closed(closing, ClosingReason.BUDGET)
        if outcome is Outcome.WORKTREE_TAKEN:
            return self._closed(run, ClosingReason.WORKTREE)
        if outcome is Outcome.WORKTREE_LEFT_BEHIND:
            return self._closed(run, ClosingReason.WORKTREE)
        if outcome is Outcome.CONFLICTING:
            return self._after_a_catch_up_conflict(run)

        return self._after_the_step_of(run, outcome, call_died=call_died)

    @staticmethod
    def _marking_a_dead_call(run: Run, call_died: bool) -> Run:
        if call_died:
            return replace(run, previous_call_died=True)

        return run

    def _after_a_catch_up_conflict(self, run: Run) -> Transition:
        match run.step:
            case (
                Step.MOUNT_WORKTREE
                | Step.UNDERSTAND
                | Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.CATCH_UP
            ):
                return self._closed(run, ClosingReason.CI_CONFLICT)
            case Step.AWAIT_CI:
                return self._retrying_a_catch_up(run)
            case Step.AWAIT_MERGE:
                self._impossible(run, Outcome.CONFLICTING)

    def _retrying_a_catch_up(self, run: Run) -> Transition:
        if run.catch_up_retries < self.budgets.catch_up_retries:
            moved = replace(run, catch_up_retries=run.catch_up_retries + 1, step=Step.CATCH_UP)
            return Transition(run=moved, wait_seconds=self.budgets.seconds_between_ticks)

        return self._closed(run, ClosingReason.CI_CONFLICT)

    def reopened(self, run: Run, *, blocked: IssueLabel) -> Run:
        match blocked:
            case (
                IssueLabel.BLOCKED_CONTROLS
                | IssueLabel.BLOCKED_JUDGE
                | IssueLabel.BLOCKED_CI_RED
                | IssueLabel.BLOCKED_CI_INDETERMINATE
                | IssueLabel.BLOCKED_CI_CONFLICT
            ):
                return self._with_the_retry_counter_reset(run, blocked=blocked)
            case IssueLabel.ABORTED_BUDGET:
                return replace(run, spend=HarnessSpend.nothing())
            case IssueLabel.ABORTED_UNMEASURED_CALL | IssueLabel.BLOCKED_WORKTREE:
                return run
            case _:
                raise ImpossibleTransitionError(f"the label `{blocked}` names no closed run that can be reopened")

    @staticmethod
    def _with_the_retry_counter_reset(
        run: Run,
        *,
        blocked: Literal[
            IssueLabel.BLOCKED_CONTROLS,
            IssueLabel.BLOCKED_JUDGE,
            IssueLabel.BLOCKED_CI_RED,
            IssueLabel.BLOCKED_CI_INDETERMINATE,
            IssueLabel.BLOCKED_CI_CONFLICT,
        ],
    ) -> Run:
        match blocked:
            case IssueLabel.BLOCKED_CONTROLS:
                return replace(
                    run, control_retries=0, hygiene_retries=0, catching_up_the_branch=False, step=Step.IMPLEMENT
                )
            case IssueLabel.BLOCKED_JUDGE:
                return replace(run, verify_retries=0)
            case IssueLabel.BLOCKED_CI_RED:
                return replace(run, ci_retries=0)
            case IssueLabel.BLOCKED_CI_INDETERMINATE:
                return replace(run, indeterminate_ticks=0)
            case IssueLabel.BLOCKED_CI_CONFLICT:
                return replace(run, catch_up_retries=0, indeterminate_ticks=0)

    def _after_the_step_of(self, run: Run, outcome: Outcome, *, call_died: bool) -> Transition:
        match run.step:
            case Step.MOUNT_WORKTREE:
                return self._after_mounting_the_worktree(run, outcome)
            case Step.UNDERSTAND:
                self._impossible(run, outcome)
            case Step.IMPLEMENT | Step.RUN_CONTROLS | Step.VERIFY:
                return self._after_producing(run, outcome, run.step, call_died=call_died)
            case Step.OPEN_PULL_REQUEST | Step.AWAIT_CI | Step.CATCH_UP | Step.AWAIT_MERGE:
                return self._after_delivering(run, outcome, run.step)

    def _after_mounting_the_worktree(self, run: Run, outcome: Outcome) -> Transition:
        if outcome is Outcome.DONE:
            return self._moving_to(run, Step.IMPLEMENT)

        self._impossible(run, outcome)

    def _after_producing(
        self,
        run: Run,
        outcome: Outcome,
        step: Literal[Step.IMPLEMENT, Step.RUN_CONTROLS, Step.VERIFY],
        *,
        call_died: bool,
    ) -> Transition:
        match step:
            case Step.IMPLEMENT:
                return self._after_implementing(run, outcome, call_died=call_died)
            case Step.RUN_CONTROLS:
                return self._after_the_controls(run, outcome)
            case Step.VERIFY:
                return self._after_the_judge(run, outcome, call_died=call_died)

    def _after_delivering(
        self,
        run: Run,
        outcome: Outcome,
        step: Literal[Step.OPEN_PULL_REQUEST, Step.AWAIT_CI, Step.CATCH_UP, Step.AWAIT_MERGE],
    ) -> Transition:
        match step:
            case Step.OPEN_PULL_REQUEST:
                return self._after_the_pull_request(run, outcome)
            case Step.AWAIT_CI:
                return self._after_asking_the_ci(run, outcome)
            case Step.CATCH_UP:
                return self._after_catching_up_the_branch(run, outcome)
            case Step.AWAIT_MERGE:
                return self._after_asking_for_the_merge(run, outcome)

    def _after_catching_up_the_branch(self, run: Run, outcome: Outcome) -> Transition:
        if outcome is Outcome.DONE:
            return self._moving_to(replace(run, catching_up_the_branch=True), Step.RUN_CONTROLS)

        self._impossible(run, outcome)

    def _after_implementing(self, run: Run, outcome: Outcome, *, call_died: bool) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(replace(run, previous_call_died=False, retry_instruction=""), Step.RUN_CONTROLS)
            case Outcome.DISCARDED:
                return self._moving_to(
                    replace(run, implement_discards=run.implement_discards + 1, previous_call_died=True),
                    Step.IMPLEMENT,
                )
            case Outcome.CALL_NOT_MEASURED:
                return self._closed(self._marking_a_dead_call(run, call_died), ClosingReason.UNMEASURED_CALL)
            case _:
                self._impossible(run, outcome)

    def _after_the_controls(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._after_controls_pass(self._logged_a_round(run))
            case Outcome.FAILED:
                return self._retrying_a_mechanical_failure(self._logged_a_round(run))
            case Outcome.HYGIENE_REJECTED:
                return self._retrying_a_hygiene_rejection(run)
            case Outcome.INDETERMINATE:
                return self._ticking(self._logged_a_round(run))
            case _:
                self._impossible(run, outcome)

    @staticmethod
    def _logged_a_round(run: Run) -> Run:
        return replace(run, control_rounds_logged=run.control_rounds_logged + 1)

    def _after_controls_pass(self, run: Run) -> Transition:
        if run.catching_up_the_branch:
            return self._moving_to(run, Step.OPEN_PULL_REQUEST)
        if run.correcting_review:
            return self._moving_to(replace(run, requested_changes=()), Step.OPEN_PULL_REQUEST)

        return self._moving_to(run, Step.VERIFY)

    def _retrying_a_mechanical_failure(self, run: Run) -> Transition:
        if run.control_retries < self.budgets.control_retries:
            return self._moving_to(
                replace(run, control_retries=run.control_retries + 1, catching_up_the_branch=False), Step.IMPLEMENT
            )

        return self._closed(run, ClosingReason.CONTROLS)

    def _retrying_a_hygiene_rejection(self, run: Run) -> Transition:
        if run.hygiene_retries < self.budgets.hygiene_retries:
            return self._moving_to(
                replace(run, hygiene_retries=run.hygiene_retries + 1, catching_up_the_branch=False), Step.IMPLEMENT
            )

        return self._closed(run, ClosingReason.CONTROLS)

    def _after_the_judge(self, run: Run, outcome: Outcome, *, call_died: bool) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(self._logged_a_verify_round(run), Step.OPEN_PULL_REQUEST)
            case Outcome.DISCARDED:
                return self._moving_to(replace(run, verify_discards=run.verify_discards + 1), Step.VERIFY)
            case Outcome.FAILED:
                return self._retrying_a_veto(self._logged_a_verify_round(run))
            case Outcome.UNCHANGED:
                return self._closed(run, ClosingReason.JUDGE)
            case Outcome.CALL_NOT_MEASURED:
                return self._closed(self._marking_a_dead_call(run, call_died), ClosingReason.UNMEASURED_CALL)
            case _:
                self._impossible(run, outcome)

    @staticmethod
    def _logged_a_verify_round(run: Run) -> Run:
        return replace(run, verify_rounds_logged=run.verify_rounds_logged + 1)

    def _retrying_a_veto(self, run: Run) -> Transition:
        if run.verify_retries < self.budgets.verify_retries:
            return self._moving_to(replace(run, verify_retries=run.verify_retries + 1), Step.IMPLEMENT)

        return self._closed(run, ClosingReason.JUDGE)

    def _after_the_pull_request(self, run: Run, outcome: Outcome) -> Transition:
        if outcome is Outcome.DONE:
            return self._moving_to(replace(run, catching_up_the_branch=False), Step.AWAIT_CI)

        self._impossible(run, outcome)

    def _after_asking_the_ci(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(self._answered(run), Step.AWAIT_MERGE)
            case Outcome.PENDING:
                return self._ticking(self._answered(run))
            case Outcome.INDETERMINATE:
                return self._counting_a_tick_with_no_answer(run)
            case Outcome.FAILED:
                return self._retrying_a_red_ci(self._answered(run))
            case _:
                self._impossible(run, outcome)

    def _counting_a_tick_with_no_answer(self, run: Run) -> Transition:
        counted = replace(run, indeterminate_ticks=run.indeterminate_ticks + 1)
        if counted.indeterminate_ticks < self.budgets.indeterminate_ticks:
            return self._ticking(counted)

        return self._closed(counted, ClosingReason.CI_INDETERMINATE)

    def _retrying_a_red_ci(self, run: Run) -> Transition:
        if run.ci_retries < self.budgets.ci_retries:
            return self._moving_to(replace(run, ci_retries=run.ci_retries + 1), Step.IMPLEMENT)

        return self._closed(run, ClosingReason.CI_RED)

    def _after_asking_for_the_merge(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return Transition(run=run, closure=Closure.merged())
            case Outcome.PENDING:
                return self._ticking(run)
            case Outcome.CHANGES_REQUESTED:
                return self._moving_to(run, Step.IMPLEMENT)
            case _:
                self._impossible(run, outcome)

    @staticmethod
    def _answered(run: Run) -> Run:
        return replace(run, indeterminate_ticks=0)

    @staticmethod
    def _moving_to(run: Run, step: Step) -> Transition:
        return Transition(run=replace(run, step=step))

    def _ticking(self, run: Run) -> Transition:
        return Transition(run=run, wait_seconds=self.budgets.seconds_between_ticks)

    @staticmethod
    def _closed(run: Run, reason: ClosingReason) -> Transition:
        return Transition(run=run, closure=Closure.because_of(reason))

    @staticmethod
    def _impossible(run: Run, outcome: Outcome) -> NoReturn:
        raise ImpossibleTransitionError(f"the step `{run.step}` cannot come back with the outcome `{outcome}`")
