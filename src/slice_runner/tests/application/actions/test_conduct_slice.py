from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.effort import Effort
from slice_runner.domain.exceptions import (
    CiCommandFailedError,
    DirtyIndexError,
    ImpossibleTransitionError,
    NoPullRequestError,
    NoSliceLeftError,
    UnchangedDiffError,
    UnreadableCiError,
)
from slice_runner.domain.feature_slice import FeatureSlice
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run import Run
from slice_runner.domain.state_machine import StateMachine
from slice_runner.domain.step import Step
from slice_runner.tests.conductor import Conductor
from slice_runner.tests.mothers.branch_catch_up_mother import BranchCatchUpMother
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother
from slice_runner.tests.mothers.pull_request_review_mother import PullRequestReviewMother
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother
from slice_runner.tests.mothers.rejection_mother import RejectionMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.select_slice_result_mother import SelectSliceResultMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother, VerificationMother

_RETRY_INSTRUCTION = "el control ya esta arreglado a mano"

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.implementation import Implementation
    from slice_runner.domain.pull_request_review import PullRequestReview
    from slice_runner.domain.sub_issue import SubIssue

_SUBISSUE = SubIssueMother.pending().number
_BRANCH = "slice/05-prechecks-deterministas"


class TestConductSliceStartingANewRun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start())

    def test_a_new_run_goes_from_mounting_the_worktree_to_implementing_without_asking_for_an_understanding(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert conductor.worktrees.add_new_branch.called
        persisted_steps = [call.kwargs["run"].step for call in conductor.repository.write_run.call_args_list]
        assert Step.UNDERSTAND not in persisted_steps

    def test_a_subissue_with_no_label_yet_is_marked_in_progress_without_asking_gh_to_remove_one_that_is_not_there(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.unlabelled()))

        conductor.conduct()

        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=None, add=IssueLabel.IN_PROGRESS
        )

    def test_selecting_a_slice_marks_the_subissue_in_progress_before_the_implementer_is_asked_to_start(self) -> None:
        conductor = self._conductor()
        manager = Mock()
        manager.attach_mock(conductor.repository.write_label, "write_label")
        manager.attach_mock(conductor.implement.execute, "implement")

        conductor.conduct()

        assert [call[0] for call in manager.mock_calls][:2] == ["write_label", "implement"]
        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

    def test_reinvoking_a_subissue_already_marked_in_progress_does_not_write_the_label_again(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.carrying(IssueLabel.IN_PROGRESS))
        )

        conductor.conduct()

        assert IssueLabel.IN_PROGRESS not in [
            call.kwargs.get("add") for call in conductor.repository.write_label.call_args_list
        ]
        assert conductor.implement.execute.call_count == 1

    def test_the_precheck_is_asked_about_the_declared_base_before_anything_is_mounted(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.prechecks.execute.call_args.args[0]
        assert asked.base == Conductor.BASE

    def test_a_precheck_that_is_not_clear_ends_the_invocation_without_mounting_or_writing_anything(self) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN)

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (
            Halt.PRECHECKS_BLOCKED,
            PrecheckResult(outcome=PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN),
        )
        assert not conductor.worktrees.add_new_branch.called
        assert conductor.repository.write_run.call_count == 0

    def test_a_precheck_with_no_reason_writes_nothing_to_the_subissue_beyond_the_halt_itself(self) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN)

        conductor.conduct()

        assert conductor.repository.write_precheck_reason.call_count == 0

    def test_a_precheck_stopped_by_an_unreadable_source_writes_the_outcome_and_the_reason_on_the_subissue(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.check_sources.execute.return_value = PrecheckResult(
            outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md does not exist under the worktree"
        )

        conductor.conduct()

        conductor.repository.write_precheck_reason.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            outcome=PrecheckOutcome.UNREADABLE_SOURCE,
            reason="CLAUDE.md does not exist under the worktree",
        )


class TestConductSliceHandingTheDecisionsToTheImplementer:
    def test_the_implementer_of_a_resumed_run_receives_the_decisions_of_the_parent_and_the_subissue(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))

        conductor.conduct()

        implemented = conductor.implement.execute.call_args.args[0]
        assert implemented.parent.decisions + implemented.subissue.decisions == (
            ParentIssueMother.with_sources_and_controls().decisions + SubIssueMother.pending().decisions
        )


class TestConductSliceHandingTheDesignsToEveryAgent:
    def test_the_sources_check_counts_the_designs_the_subissue_names_and_not_the_whole_parent(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.about_to_start(
                subissue=SubIssueMother.naming_designs("detalle"), parent=ParentIssueMother.declaring_two_designs()
            )
        )

        conductor.conduct()

        assert conductor.check_sources.execute.call_args.args[0].designs == (DesignMother.detail(),)

    def test_the_judge_gets_the_designs_the_subissue_names(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            )
        )

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].designs == (DesignMother.detail(),)

    def test_the_captures_are_read_from_the_worktree_for_the_designs_the_subissue_names(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            )
        )

        conductor.conduct()

        asked = conductor.read_captures.execute.call_args.args[0]
        assert (asked.worktree, asked.designs) == (Conductor.WORKTREE, (DesignMother.detail(),))

    def test_what_is_read_of_the_captures_reaches_the_judge(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            )
        )
        conductor.read_captures.execute.return_value = DesignCapturesMother.missing()

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].captures == DesignCapturesMother.missing()


class TestConductSliceResumingARunLeftAtTheRetiredUnderstandStep:
    def test_the_run_is_refused_instead_of_being_driven_through_a_step_this_program_no_longer_runs(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(Run(step=Step.UNDERSTAND)))

        with pytest.raises(ImpossibleTransitionError):
            conductor.conduct()

        assert conductor.implement.execute.call_count == 0


class TestConductSliceClosingAMergeMissedBetweenInvocations:
    @staticmethod
    def _conductor(*, dangling: tuple[SubIssue, ...], models: RoleModels | None = None) -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(dangling=dangling), models=models)
        conductor.check_sources.execute.return_value = PrecheckResult(
            outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="stops the run once the dangling slices are reconciled"
        )

        return conductor

    def test_a_dangling_subissue_whose_pull_request_merged_writes_its_durable_row_as_merged(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.repo, recorded.slice_id, recorded.name, recorded.closure, recorded.run) == (
            Conductor.REPO,
            dangling.slice_id.canonical,
            dangling.slice_id.name,
            Closure.merged(),
            dangling.run,
        )

    def test_a_dangling_subissue_whose_pull_request_merged_writes_the_findings_the_corpus_already_had_for_it(
        self,
    ) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        raised = FindingMother.without_line()
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing(raised))

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert recorded.findings == (raised,)

    def test_a_dangling_subissue_whose_pull_request_merged_writes_the_budgets_and_models_this_invocation_ran_with(
        self,
    ) -> None:
        dangling = SubIssueMother.dangling()
        models = RoleModels(implement="opus", verify="opus", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH)
        conductor = self._conductor(dangling=(dangling,), models=models)

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.budgets, recorded.models) == (conductor.budgets, models)

    def test_a_dangling_subissue_whose_pull_request_merged_drops_the_label_it_still_carried(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.repository.remove_label.assert_any_call(
            repo=Conductor.REPO, issue=dangling.number, remove=dangling.label
        )

    def test_a_dangling_subissue_whose_pull_request_merged_clears_its_run_so_it_stops_being_dangling(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.repository.clear_run.assert_any_call(repo=Conductor.REPO, issue=dangling.number)

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_is_left_untouched(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0
        assert conductor.repository.remove_label.call_count == 0

    def test_a_dangling_subissue_with_no_pull_request_found_for_its_branch_is_left_untouched(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.any_pull_request.return_value = None

        conductor.conduct()

        assert conductor.forum.pull_request_state.call_count == 0
        assert conductor.metrics.record.call_count == 0

    def test_the_pull_request_asked_about_is_the_one_open_on_the_dangling_subissues_own_branch(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.forum.any_pull_request.assert_any_call(repo=Conductor.REPO, branch=dangling.branch)

    def test_an_invocation_with_nothing_dangling_neither_records_nor_removes_a_label_for_it(self) -> None:
        conductor = self._conductor(dangling=())

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0
        assert conductor.repository.remove_label.call_count == 0

    def test_a_dangling_subissue_whose_pull_request_merged_also_asks_to_close_the_parent_of_this_issue(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.close.execute.assert_any_call(CloseParentParams(repo=Conductor.REPO, issue=Conductor.ISSUE))

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_asks_to_close_nothing(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        conductor.conduct()

        assert conductor.close.execute.call_count == 0

    def test_a_dangling_subissue_whose_pull_request_merged_leaves_one_closing_event_as_merged_with_its_feature_and_name(
        self,
    ) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        merged = [event for event in conductor.emitted_events if event.closure == Closure.merged()]
        assert [(event.slice_id, event.feature_slice) for event in merged] == [
            (
                dangling.slice_id.canonical,
                FeatureSlice(parent=Conductor.ISSUE, name=dangling.slice_id.name),
            )
        ]

    def test_two_invocations_in_a_row_leave_exactly_one_merged_closing_event_for_the_reconciled_slice(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.select.execute.side_effect = lambda _params: SelectSliceResultMother.about_to_start(
            dangling=() if conductor.repository.clear_run.called else (dangling,)
        )

        conductor.conduct()
        conductor.conduct()

        merged = [event for event in conductor.emitted_events if event.closure == Closure.merged()]
        assert len(merged) == 1

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_leaves_no_merged_closing_event(
        self,
    ) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        conductor.conduct()

        assert [event for event in conductor.emitted_events if event.closure == Closure.merged()] == []

    def test_a_dangling_subissue_with_no_pull_request_found_leaves_no_merged_closing_event(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.any_pull_request.return_value = None

        conductor.conduct()

        assert [event for event in conductor.emitted_events if event.closure == Closure.merged()] == []


class TestConductSliceWhenTheNamedSliceCannotBeSelected:
    @staticmethod
    def _unselectable(*, dangling: tuple[SubIssue, ...]) -> NoSliceLeftError:
        error = NoSliceLeftError("slice-12 of issue 38 cannot be run: it is closed, blocked or aborted")
        error.dangling = dangling

        return error

    def test_a_run_left_dangling_still_closes_and_writes_its_row_instead_of_the_selection_failing_silently(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        dangling = SubIssueMother.dangling()
        conductor.select.execute.side_effect = self._unselectable(dangling=(dangling,))

        with pytest.raises(NoSliceLeftError):
            conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.slice_id, recorded.closure) == (dangling.slice_id.canonical, Closure.merged())

    def test_the_slice_that_cannot_be_selected_still_fails_the_invocation_once_the_dangling_run_is_closed(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))

        with pytest.raises(NoSliceLeftError, match="slice-12"):
            conductor.conduct()

    def test_nothing_left_dangling_records_no_row_before_the_selection_failure_propagates(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=())

        with pytest.raises(NoSliceLeftError):
            conductor.conduct()

        assert conductor.metrics.record.call_count == 0

    def test_the_failure_after_reconciling_a_dangling_run_says_how_many_it_reconciled_before_giving_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))

        with pytest.raises(NoSliceLeftError, match="reconciled 1"):
            conductor.conduct()

    def test_the_failure_with_nothing_dangling_says_it_reconciled_zero_before_giving_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=())

        with pytest.raises(NoSliceLeftError, match="reconciled 0"):
            conductor.conduct()

    def test_a_dangling_run_whose_pull_request_closed_without_merging_is_not_counted_as_reconciled(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        with pytest.raises(NoSliceLeftError, match="reconciled 0"):
            conductor.conduct()


class TestConductSliceResumingARunReopenedByAnEarlierInvocation:
    def test_a_fresh_invocation_resuming_a_run_reopened_by_an_earlier_one_still_names_the_round_after_the_ones_logged(
        self,
    ) -> None:
        reopened_run = replace(RunMother.blocked_on_controls(), control_retries=0)
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(reopened_run))

        conductor.conduct()

        slice_dir = Conductor.slice_dir(SubIssueMother.pending().slice_id)
        assert conductor.controls.run.call_args_list[0].kwargs["out"] == slice_dir / "round-4"


class TestConductSliceResumingAReopenedRun:
    @staticmethod
    def _reopened_blocked_on_verify() -> Run:
        return replace(RunMother.blocked_on_verify(), verify_retries=0, retry_instruction=_RETRY_INSTRUCTION)

    def test_the_run_resumes_with_the_retry_budget_the_reopening_restored(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(self._reopened_blocked_on_verify()))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing()),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert conductor.implement.execute.call_count == 1

    def test_the_instruction_persisted_in_the_run_travels_to_the_implementer(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing_after_a_retry(_RETRY_INSTRUCTION))
        )

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].retry_instruction == _RETRY_INSTRUCTION

    def test_a_run_that_died_before_implementing_hands_the_instruction_over_when_launched_again(self) -> None:
        dying = Conductor(chosen=SelectSliceResultMother.resumed_at(self._reopened_blocked_on_verify()))
        dying.verify.execute.side_effect = [VerificationMother.vetoing(VerdictMother.failing())]
        dying.implement.execute.side_effect = OSError("the process died")
        with pytest.raises(OSError, match="died"):
            dying.conduct()
        last_persisted = dying.repository.write_run.call_args_list[-1].kwargs["run"]

        relaunched = Conductor(chosen=SelectSliceResultMother.resumed_at(last_persisted))
        relaunched.conduct()

        assert relaunched.implement.execute.call_args.args[0].retry_instruction == _RETRY_INSTRUCTION

    def test_the_instruction_is_spent_once_the_implementer_has_received_it(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing_after_a_retry(_RETRY_INSTRUCTION))
        )

        conductor.conduct()

        persisted = [written.kwargs["run"] for written in conductor.repository.write_run.call_args_list]
        assert persisted[0].step is Step.RUN_CONTROLS
        assert persisted[0].retry_instruction == ""

    def test_a_later_round_of_the_implementer_does_not_receive_the_instruction_again(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing_after_a_retry(_RETRY_INSTRUCTION))
        )
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert [call.args[0].retry_instruction for call in conductor.implement.execute.call_args_list] == [
            _RETRY_INSTRUCTION,
            "",
        ]

    def test_a_run_reopened_from_blocked_on_controls_implements_before_staging_anything(self) -> None:
        blocked = replace(RunMother.blocked_on_controls(), retry_instruction=_RETRY_INSTRUCTION)
        reopened_run = StateMachine(budgets=Budgets()).reopened(blocked, blocked=IssueLabel.BLOCKED_CONTROLS)
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(reopened_run))
        order = Mock()
        order.attach_mock(conductor.implement.execute, "implement")
        order.attach_mock(conductor.stage.execute, "stage")

        conductor.conduct()

        assert [call[0] for call in order.mock_calls][:2] == ["implement", "stage"]

    def test_reopening_a_run_blocked_on_controls_names_the_next_round_after_the_ones_already_logged(self) -> None:
        reopened_run = replace(RunMother.blocked_on_controls(), control_retries=0)
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(reopened_run))

        conductor.conduct()

        slice_dir = Conductor.slice_dir(SubIssueMother.pending().slice_id)
        assert conductor.controls.run.call_args_list[0].kwargs["out"] == slice_dir / "round-4"


class TestConductSliceResumingAnInterruptedRun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()))

    def test_a_run_persisted_at_verify_judges_instead_of_implementing_and_running_the_controls_again(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert (conductor.implement.execute.call_count, conductor.controls.run.call_count) == (0, 0)
        assert conductor.verify.execute.call_count == 1

    def test_a_run_resumed_directly_at_verify_carries_no_debt_because_no_implementation_ran_this_invocation(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].debt == ()

    def test_a_run_that_was_already_aligned_does_not_go_through_the_prechecks_again(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.prechecks.execute.call_count == 0

    def test_a_persisted_run_whose_subissue_declares_another_repo_is_stopped_at_this_gate_too(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging(), subissue=SubIssueMother.of_another_repo())
        )

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (
            Halt.PRECHECKS_BLOCKED,
            PrecheckResult(outcome=PrecheckOutcome.SLICE_IN_ANOTHER_REPO),
        )
        assert conductor.verify.execute.call_count == 0
        assert conductor.repository.write_precheck_reason.call_count == 0


class TestConductSliceResumingCatchesUpTheBranch:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))

    def test_a_branch_already_caught_up_still_reaches_the_implementer(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1

    def test_a_conflicting_catch_up_closes_the_run_before_spending_any_call_on_the_harness(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CI_CONFLICT)
        assert (conductor.implement.execute.call_count, conductor.verify.execute.call_count) == (0, 0)

    def test_a_conflicting_catch_up_writes_the_conflict_label_and_records_the_closed_row(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_CONFLICT
        )
        assert conductor.metrics.record.call_args.args[0].closure == Closure.because_of(ClosingReason.CI_CONFLICT)

    def test_a_conflicting_catch_up_publishes_the_paths_git_reported_as_a_comment(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        conductor.conduct()

        conductor.repository.publish_catch_up_conflict.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, paths=BranchCatchUpMother.CONFLICTING_PATHS
        )

    def test_a_run_already_awaiting_the_ci_of_a_pull_request_already_open_is_never_asked_to_catch_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()))

        conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0

    def test_a_run_already_awaiting_the_merge_of_a_pull_request_already_open_is_never_asked_to_catch_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0


class _ResumedAwaitingTheCi:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()), budgets=budgets)


class TestConductSliceCatchesUpTheBranchWhenTheCiFindsAConflict(_ResumedAwaitingTheCi):
    def test_a_conflict_found_by_the_ci_is_caught_up_instead_of_closing_the_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 1
        assert (result.halt, result.closure, result.step) == (Halt.WAIT_EXHAUSTED, Closure.open(), Step.AWAIT_CI)

    def test_the_round_trip_after_a_conflict_never_repays_the_implementer_or_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert (conductor.implement.execute.call_count, conductor.verify.execute.call_count) == (0, 0)

    def test_a_catch_up_that_reaches_a_passing_round_commits_it_exactly_once(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.commit.execute.call_count == 1

    def test_the_retry_that_returns_to_catch_up_waits_before_asking_the_ci_again(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1, seconds_between_ticks=45))
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.clock.sleep.call_args_list[0].kwargs["seconds"] == 45

    def test_the_catch_up_retries_exhausted_closes_the_run_as_a_conflict_just_like_before(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1))
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.CI_CONFLICT)

    def test_a_conflict_found_while_catching_up_the_branch_after_a_ci_retry_publishes_its_paths(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1))
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()
        conductor.branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CI_CONFLICT)
        conductor.repository.publish_catch_up_conflict.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, paths=BranchCatchUpMother.CONFLICTING_PATHS
        )

    def test_resuming_with_a_catch_up_retry_already_spent_does_not_reset_the_counter(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.with_one_catch_up_retry_already_spent()),
            budgets=Budgets(catch_up_retries=1),
        )
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0
        assert result.closure == Closure.because_of(ClosingReason.CI_CONFLICT)

    def test_a_control_round_that_fails_after_the_catch_up_still_sends_the_repaired_round_to_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert conductor.verify.execute.call_count == 1

    def test_a_control_round_that_fails_after_the_catch_up_still_commits_the_round_that_finally_passes(
        self,
    ) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert conductor.commit.execute.call_count == 1


class TestConductSliceResumingWithSpendAlreadyPersisted:
    def test_reinvoking_does_not_reset_the_budget_because_the_prior_spend_travels_with_the_run(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)),
            budgets=Budgets(slice_cost_usd=prior.cost_usd),
        )

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 0
        assert result.closure == Closure.because_of(ClosingReason.BUDGET)

    def test_the_durable_row_of_a_reinvoked_run_still_carries_the_cost_paid_in_an_earlier_invocation(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)))
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=prior)
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.spend == HarnessSpend.summing((prior, HarnessSpendMother.of_the_judge_call()))

    def test_the_run_written_after_a_paid_call_persists_the_cumulative_spend_and_not_only_this_calls(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)))

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[0].spend == HarnessSpend.summing((prior, HarnessSpendMother.of_the_judge_call()))

    def test_the_closed_row_of_a_run_resumed_after_a_dead_invocation_counts_every_call_the_trace_holds(self) -> None:
        lost_to_the_dead_invocation = HarnessSpendMother.of_the_understanding_call()
        the_last_persisted = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(the_last_persisted))
        )
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=lost_to_the_dead_invocation)
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=the_last_persisted)

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.run.spend == HarnessSpend.summing((the_last_persisted, HarnessSpendMother.of_the_judge_call()))
        assert recorded.spend == HarnessSpend.summing((lost_to_the_dead_invocation, the_last_persisted))


class TestConductSliceOnTheHappyPath:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_it_walks_the_steps_in_the_order_the_state_machine_dictates_and_persists_each_one(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30, person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert [call.kwargs["run"].step for call in conductor.repository.write_run.call_args_list] == [
            Step.RUN_CONTROLS,
            Step.VERIFY,
            Step.OPEN_PULL_REQUEST,
            Step.AWAIT_CI,
            Step.AWAIT_MERGE,
        ]
        assert (result.closure, result.step) == (Closure.open(), Step.AWAIT_MERGE)

    def test_the_index_is_staged_with_exactly_what_the_implementer_reported(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.stage.execute.call_args.args[0].paths == ImplementationMother.of_two_paths().paths

    def test_a_control_round_that_passes_on_the_first_try_is_committed_once_with_round_one_and_verified_once(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.commit.execute.call_count == 1
        assert conductor.pull_request.commit_message.call_args.kwargs["round"] == 1
        assert conductor.verify.execute.call_count == 1

    def test_the_pull_request_is_opened_on_the_branch_of_the_slice_with_what_the_writer_composed(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        delivered = conductor.deliver.execute.call_args.args[0]
        assert (delivered.worktree, delivered.repo, delivered.branch, delivered.base) == (
            Conductor.WORKTREE,
            Conductor.REPO,
            _BRANCH,
            Conductor.BASE,
        )
        assert (delivered.title, delivered.body) == (Conductor.TITLE, Conductor.BODY)

    def test_the_comparison_is_mounted_before_the_pull_request_is_opened_with_the_designs_and_captures_of_the_round(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.about_to_open_the_pull_request(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            )
        )
        conductor.read_captures.execute.return_value = DesignCapturesMother.of_the_board_and_the_detail()

        conductor.conduct()

        mounted = conductor.mount_comparison.execute.call_args.args[0]
        assert (mounted.worktree, mounted.designs, mounted.captures) == (
            Conductor.WORKTREE,
            (DesignMother.detail(),),
            DesignCapturesMother.of_the_board_and_the_detail(),
        )

    def test_the_pull_request_body_is_asked_for_with_what_the_implementer_declared_left_out(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_debt()

        conductor.conduct()

        assert conductor.pull_request.body.call_args.kwargs["debt"] == ImplementationMother.with_debt().left_out

    def test_the_judge_gets_what_the_implementer_declared_left_out_this_invocation(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_debt()

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].debt == ImplementationMother.with_debt().left_out

    def test_the_pull_request_body_is_asked_for_with_the_deviations_the_implementer_declared(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_two_deviations()

        conductor.conduct()

        assert (
            conductor.pull_request.body.call_args.kwargs["deviations"]
            == ImplementationMother.with_two_deviations().deviations
        )

    def test_the_judge_gets_the_deviations_the_implementer_declared_this_invocation(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_two_deviations()

        conductor.conduct()

        assert (
            conductor.verify.execute.call_args.args[0].deviations
            == ImplementationMother.with_two_deviations().deviations
        )

    def test_the_judge_gets_the_decisions_of_the_parent_followed_by_those_of_the_subissue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.verify.execute.call_args.args[0]
        assert asked.decisions == (
            *ParentIssueMother.with_sources_and_controls().decisions,
            *SubIssueMother.pending().decisions,
        )

    def test_the_pull_request_it_just_opened_is_the_one_it_asks_the_ci_and_the_merge_about(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.ci.status.call_args.kwargs == {"repo": Conductor.REPO, "pull_request": Conductor.PULL_REQUEST}
        assert conductor.forum.pull_request_state.call_args.kwargs == {
            "repo": Conductor.REPO,
            "number": Conductor.PULL_REQUEST,
        }
        assert conductor.forum.open_pull_request.call_count == 0

    def test_a_green_ci_moves_the_label_to_awaiting_merge_because_the_merge_is_a_human_decision(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30, person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.AWAITING_MERGE
        )

    def test_a_merged_pull_request_closes_the_run_and_the_invocation_reports_its_number(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert (result.halt, result.closure, result.pull_request) == (
            Halt.RUN_CLOSED,
            Closure.merged(),
            Conductor.PULL_REQUEST,
        )

    def test_a_slice_carrying_a_user_story_reaches_the_judge_and_the_durable_row_by_its_canonical_identifier(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(), subissue=SubIssueMother.carrying_a_user_story()
            )
        )

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].slice_id == "PROJ-1234-05"
        assert conductor.closed.slice_id == "PROJ-1234-05"

    def test_a_slice_resumed_past_verify_still_closes_with_the_size_the_corpus_already_holds(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))
        conductor.seed_verdict(round=1, verdict=VerdictMother.passing())

        conductor.conduct()

        assert conductor.verify.execute.call_count == 0
        assert conductor.closed.diff_stats == SliceDiffMother.STATS

    def test_a_merged_run_writes_no_label_because_github_closes_the_subissue_on_the_merge(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        assert conductor.repository.write_label.call_count == 0

    def test_a_merged_run_still_removes_whatever_label_the_subissue_carried_so_the_two_do_not_contradict(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        conductor.repository.remove_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS
        )

    def test_a_merged_run_that_carried_no_label_removes_none_because_there_is_nothing_to_retire(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge(), label=None))

        conductor.conduct()

        assert conductor.repository.remove_label.call_count == 0

    def test_the_durable_row_carries_the_slice_the_state_and_every_call_that_was_paid_for(self) -> None:
        conductor = self._conductor()
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded = conductor.closed
        assert (recorded.repo, recorded.slice_id, recorded.name) == (
            Conductor.REPO,
            "slice-05",
            "prechecks-deterministas",
        )
        assert recorded.closure == Closure.merged()
        assert recorded.spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_the_durable_row_carries_the_budgets_and_the_models_this_invocation_ran_with(self) -> None:
        models = RoleModels(implement="opus", verify="opus", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH)
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()),
            budgets=Budgets(slice_cost_usd=99.0),
            models=models,
        )

        conductor.conduct()

        recorded = conductor.closed
        assert (recorded.budgets, recorded.models) == (conductor.budgets, models)

    def test_the_durable_row_carries_how_much_the_verified_diff_changed(self) -> None:
        conductor = self._conductor()
        conductor.seed_verdict(round=1, verdict=VerdictMother.passing())

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.diff_stats == SliceDiffMother.STATS

    def test_the_durable_row_carries_no_debt_the_conductor_never_asked_the_ledger_to_write(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_debt()

        conductor.conduct()

        recorded = conductor.closed
        assert (recorded.debt.declared, recorded.debt.left_out) == (False, ())

    def test_the_durable_row_carries_what_was_already_written_to_the_ledger_before_the_run_was_conducted(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.seed_debt(left_out=("el cableado del subcomando queda para otra slice",))

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.debt.left_out == ("el cableado del subcomando queda para otra slice",)

    def test_the_verification_asked_for_carries_the_subissue_number_and_not_the_parent_issue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.verify.execute.call_args.args[0]
        assert (asked.repo, asked.issue, asked.worktree) == (Conductor.REPO, _SUBISSUE, Conductor.WORKTREE)
        assert asked.issue != Conductor.ISSUE

    def test_the_verification_diffs_against_the_remote_of_the_declared_base_and_not_the_local_copy(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.verify.execute.call_args.args[0]
        assert asked.base == f"origin/{Conductor.BASE}"

    def test_the_durable_row_carries_the_subissue_number_and_not_the_parent_issue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.issue == _SUBISSUE
        assert recorded.issue != Conductor.ISSUE


class TestConductSliceReportingEvents:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_every_transition_reports_the_slice_the_step_it_lands_on_the_instant_and_the_spend_paid_so_far(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        after_the_implementer = HarnessSpendMother.of_the_implementer_call()
        after_the_judge = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )
        emitted = conductor.emitted_events
        assert [(e.slice_id, e.step, e.at, e.spend) for e in emitted] == [
            ("slice-05", Step.IMPLEMENT, Conductor.NOW, HarnessSpend.nothing()),
            ("slice-05", Step.RUN_CONTROLS, Conductor.NOW, after_the_implementer),
            ("slice-05", Step.VERIFY, Conductor.NOW, after_the_implementer),
            ("slice-05", Step.OPEN_PULL_REQUEST, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_CI, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_MERGE, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_MERGE, Conductor.NOW, after_the_judge),
        ]

    def test_every_event_names_the_parent_issue_of_the_feature_and_the_name_of_the_slice(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        expected = FeatureSlice(parent=Conductor.ISSUE, name=SubIssueMother.pending().slice_id.name)
        assert {e.feature_slice for e in conductor.emitted_events} == {expected}

    def test_the_events_before_the_pull_request_is_opened_carry_none_and_every_later_one_carries_its_number(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert [e.pull_request for e in conductor.emitted_events] == [None] * 4 + [Conductor.PULL_REQUEST] * 3

    def test_a_slice_with_a_design_carries_the_absolute_path_of_the_page_from_opening_the_pull_request_on(
        self,
    ) -> None:
        conductor = self._conductor_citing_a_design()

        conductor.conduct()

        page = DesignCapturesDirectory.comparison_of(Conductor.WORKTREE)
        assert [e.comparison for e in conductor.emitted_events] == [None] * 4 + [page] * 3
        assert [(e.step, e.comparison) for e in conductor.emitted_events if e.comparison is not None] == [
            (Step.AWAIT_CI, page),
            (Step.AWAIT_MERGE, page),
            (Step.AWAIT_MERGE, page),
        ]

    def test_a_slice_citing_no_design_carries_no_page_in_any_event(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert {e.comparison for e in conductor.emitted_events} == {None}

    def test_a_run_resumed_awaiting_the_merge_of_a_slice_with_a_design_carries_the_page_from_its_first_event(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.awaiting_merge(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            ),
            budgets=Budgets(person_wait_seconds=30),
        )
        conductor.forum.any_pull_request.return_value = 77
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        conductor.conduct()

        assert conductor.emitted_events[0].comparison == DesignCapturesDirectory.comparison_of(Conductor.WORKTREE)

    @staticmethod
    def _conductor_citing_a_design() -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(),
                subissue=SubIssueMother.naming_designs("detalle"),
                parent=ParentIssueMother.declaring_two_designs(),
            )
        )

    def test_a_run_resumed_awaiting_the_merge_carries_in_its_first_event_the_number_the_branch_search_returned(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()),
            budgets=Budgets(person_wait_seconds=30),
        )
        conductor.forum.any_pull_request.return_value = 77
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        conductor.conduct()

        assert conductor.emitted_events[0].pull_request == 77

    def test_every_event_carries_the_pid_of_the_process_that_wrote_it(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert {e.pid for e in conductor.emitted_events} == {Conductor.PID}

    def test_the_happy_path_reports_every_step_open_until_the_run_closes_as_merged(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        emitted = conductor.emitted_events
        assert [e.closure for e in emitted] == [Closure.open()] * 6 + [Closure.merged()]

    def test_a_pending_merge_reports_the_await_merge_step_still_open(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        conductor.conduct()

        emitted = conductor.emitted_events
        assert (emitted[-1].step, emitted[-1].closure) == (Step.AWAIT_MERGE, Closure.open())

    def test_a_pending_ci_that_ticks_three_times_reports_the_await_ci_step_once(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(ci_wait_seconds=90),
        )
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.clock.sleep.call_count == 3
        emitted = conductor.emitted_events
        assert [(e.step, e.closure) for e in emitted] == [(Step.AWAIT_CI, Closure.open())]

    def test_a_ci_that_waits_goes_through_catch_up_and_waits_again_reports_await_ci_twice(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(ci_wait_seconds=60),
        )
        conductor.ci.status.side_effect = [CiStatus.PENDING, CiStatus.NO_CHECKS, CiStatus.PENDING, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert [e.step for e in conductor.emitted_events].count(Step.AWAIT_CI) == 2

    def test_a_merge_wait_that_ticks_until_exhausted_reports_await_merge_once(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()),
            budgets=Budgets(person_wait_seconds=90),
        )
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert result.halt is Halt.WAIT_EXHAUSTED
        assert conductor.clock.sleep.call_count == 3
        assert [(e.step, e.closure) for e in conductor.emitted_events] == [(Step.AWAIT_MERGE, Closure.open())]


class TestConductSliceClosingTheParentAfterAMerge:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

    def test_a_merged_run_asks_to_close_the_parent_of_the_issue_this_slice_belongs_to(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.close.execute.assert_called_once_with(CloseParentParams(repo=Conductor.REPO, issue=Conductor.ISSUE))

    def test_a_merged_run_clears_its_persisted_run_so_the_next_invocation_does_not_see_it_as_dangling(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.clear_run.assert_called_once_with(repo=Conductor.REPO, issue=_SUBISSUE)

    def test_a_close_that_does_not_merge_the_slice_asks_to_close_nothing(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(hygiene_retries=0)
        )
        conductor.stage.execute.side_effect = DirtyIndexError("src/leftover.py (not-declared)")

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)
        assert conductor.close.execute.call_count == 0


class TestConductSliceImplementing:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_broken_implementation_call_is_discarded_and_retried_within_budget(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            ImplementationMother.of_two_paths(),
        ]
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_DISCARDED_IMPLEMENTER,
            spend=HarnessSpendMother.of_a_call_that_cost_nothing(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        assert conductor.implement.execute.call_count == 2
        recorded = conductor.closed
        assert recorded.run.implement_discards == 1
        assert recorded.run.discarded_call is not None
        assert recorded.run.discarded_call.step is Step.IMPLEMENT
        assert recorded.run.discarded_call.cause is DiscardCause.FAILED_CALL
        assert recorded.spend == HarnessSpend.summing(
            (
                HarnessSpendMother.of_a_call_that_cost_nothing(),
                HarnessSpendMother.of_the_implementer_call(),
                HarnessSpendMother.of_the_judge_call(),
            )
        )

    def test_the_retry_after_a_broken_call_is_told_the_previous_call_died_and_the_flag_clears_once_it_delivers(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            ImplementationMother.of_two_paths(),
        ]

        conductor.conduct()

        first_round, retried = conductor.implement.execute.call_args_list
        assert first_round.args[0].previous_call_died is False
        assert retried.args[0].previous_call_died is True
        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[-1].previous_call_died is False

    def test_a_call_killed_from_outside_leaves_the_flag_on_even_though_the_run_closes_for_an_unmeasured_call(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = RejectionMother.envelope_nobody_could_parse()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.UNMEASURED_CALL)
        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[-1].previous_call_died is True


class TestConductSliceWhenTheControlsComeBackRed:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_the_log_of_the_red_control_reaches_the_next_implementation_as_a_path(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        retried = conductor.implement.execute.call_args_list[-1].args[0]
        assert retried.control_logs == (ControlOutcomeMother.LOG,)

    def test_resuming_a_run_with_rounds_already_logged_names_the_next_round_not_round_one(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.running_the_controls_with_one_round_already_logged())
        )

        conductor.conduct()

        assert conductor.controls.run.call_args_list[0].kwargs["out"] == (
            Conductor.slice_dir(SubIssueMother.pending().slice_id) / "round-2"
        )

    def test_the_exhausted_control_budget_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CONTROLS
        )
        assert conductor.metrics.record.call_args.args[0].closure == Closure.because_of(ClosingReason.CONTROLS)

    def test_a_repo_exempt_from_controls_goes_straight_to_the_judge(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.running_the_controls(), parent=ParentIssueMother.with_exempt_controls()
            )
        )

        conductor.conduct()

        assert conductor.verify.execute.call_count == 1

    def test_a_control_round_that_comes_back_red_leaves_no_commit_because_nothing_passed_yet(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        assert conductor.commit.execute.call_count == 0

    def test_a_control_round_that_passes_after_a_retry_commits_with_the_ordinal_of_that_round(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert conductor.commit.execute.call_count == 1
        assert conductor.pull_request.commit_message.call_args.kwargs["round"] == 2


class TestConductSliceRescuesWorkLeftStagedBeforeResumingPastTheControls:
    STAGED = ("src/mod.py", "src/tests/test_mod.py")

    @classmethod
    def _conductor(cls, run: Run) -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(run))
        conductor.workspace.staged.return_value = cls.STAGED
        return conductor

    @pytest.mark.parametrize(
        "run",
        [
            RunMother.judging_after_one_control_round(),
            RunMother.about_to_open_the_pull_request(),
            RunMother.about_to_ask_the_ci_after_one_control_round(),
        ],
        ids=["verify", "open-pull-request", "await-ci"],
    )
    def test_a_run_resumed_past_the_controls_with_a_full_index_commits_it_before_anything_else(self, run: Run) -> None:
        conductor = self._conductor(run)

        conductor.conduct()

        conductor.workspace.commit.assert_called_once_with(
            worktree=Conductor.WORKTREE, message=conductor.pull_request.commit_message.return_value
        )
        assert conductor.pull_request.commit_message.call_args.kwargs["round"] == 1

    def test_a_run_left_half_way_before_this_change_with_a_full_index_and_no_commit_does_not_deliver_without_its_code(
        self,
    ) -> None:
        conductor = self._conductor(RunMother.about_to_open_the_pull_request())
        order = Mock()
        order.attach_mock(conductor.workspace.commit, "commit")
        order.attach_mock(conductor.deliver.execute, "deliver")

        conductor.conduct()

        assert [call[0] for call in order.mock_calls] == ["commit", "deliver"]

    def test_a_run_resumed_past_the_controls_with_a_clean_index_leaves_no_commit(self) -> None:
        conductor = self._conductor(RunMother.judging_after_one_control_round())
        conductor.workspace.staged.return_value = ()

        conductor.conduct()

        conductor.workspace.commit.assert_not_called()

    def test_a_run_resumed_before_the_controls_leaves_the_commit_to_the_round_that_runs_them(self) -> None:
        conductor = self._conductor(RunMother.implementing())

        conductor.conduct()

        conductor.workspace.commit.assert_not_called()
        assert conductor.commit.execute.call_count == 1

    def test_a_run_already_awaiting_the_merge_is_never_asked_to_commit(self) -> None:
        conductor = self._conductor(RunMother.awaiting_merge())

        conductor.conduct()

        conductor.workspace.commit.assert_not_called()


class TestConductSliceCommitsEveryRoundOfARun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(verify_retries=1)
        )

    def test_two_rounds_of_one_run_leave_two_commits_each_with_the_ordinal_of_its_round(self) -> None:
        conductor = self._conductor()
        raised = FindingMother.without_line()
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.commit.execute.call_count == 2
        assert [c.kwargs["round"] for c in conductor.pull_request.commit_message.call_args_list] == [1, 2]

    def test_the_pull_request_is_still_opened_once_after_two_committed_rounds(self) -> None:
        conductor = self._conductor()
        raised = FindingMother.without_line()
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.deliver.execute.call_count == 1


class TestConductSliceWhenTheStagedIndexIsRejected:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_dirty_index_fails_the_step_without_running_a_single_control(self) -> None:
        conductor = self._conductor(budgets=Budgets(hygiene_retries=0))
        conductor.stage.execute.side_effect = DirtyIndexError("the staged index is not what the implementer reported")

        result = conductor.conduct()

        assert conductor.controls.run.call_count == 0
        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)

    def test_a_rejection_spends_no_retry_of_the_controls_even_when_their_own_budget_is_exhausted(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None]

        result = conductor.conduct()

        assert result.closure == Closure.merged()

    def test_the_reason_the_index_was_refused_reaches_the_next_implementer_so_it_does_not_repeat_it(self) -> None:
        conductor = self._conductor()
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None]

        conductor.conduct()

        ordered = [call.args[0].hygiene_refusal for call in conductor.implement.execute.call_args_list]
        assert ordered[0] == ""
        assert "src/leftover.py (not-declared)" in ordered[1]

    def test_the_refusal_does_not_travel_to_a_round_whose_controls_did_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=2))
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None, None]
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        ordered = [call.args[0].hygiene_refusal for call in conductor.implement.execute.call_args_list]
        assert ordered[2] == ""

    def test_the_exhausted_hygiene_budget_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(hygiene_retries=0))
        conductor.stage.execute.side_effect = DirtyIndexError("src/leftover.py (not-declared)")

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CONTROLS
        )
        assert conductor.metrics.record.call_args.args[0].closure == Closure.because_of(ClosingReason.CONTROLS)

    def test_a_dirty_index_in_a_later_round_does_not_add_a_second_commit_and_blocks_on_hygiene(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(hygiene_retries=0))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing(raised))
        conductor.stage.execute.side_effect = [None, DirtyIndexError("src/leftover.py (not-declared)")]

        result = conductor.conduct()

        assert conductor.commit.execute.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)


class TestConductSliceWhenAControlCannotBeMeasured:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_control_that_never_settles_waits_out_the_invocation_instead_of_blocking_the_slice(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.controls.run.return_value = ControlOutcomeMother.unknown()

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_red_control_still_blocks_even_when_another_one_could_not_run(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(), parent=ParentIssueMother.with_two_controls()
            ),
            budgets=Budgets(control_retries=0),
        )
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.unknown()]

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CONTROLS)


class TestConductSliceWhenTheJudgeSpeaks:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()), budgets=budgets)

    def test_two_verifications_of_the_same_run_are_asked_for_round_one_and_round_two_in_order(self) -> None:
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing()),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        rounds = [call.args[0].verify_round for call in conductor.verify.execute.call_args_list]
        assert rounds == [1, 2]

    def test_the_first_verification_carries_no_prior_findings_and_the_second_carries_what_the_first_raised(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        carried = [call.args[0].prior_findings for call in conductor.verify.execute.call_args_list]
        assert carried == [(), (raised,)]

    def test_a_discarded_verdict_asks_the_retry_for_the_same_round_it_discarded_because_nothing_got_recorded(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.incoherent_verdict(), VerificationMother.passing()]

        conductor.conduct()

        rounds = [call.args[0].verify_round for call in conductor.verify.execute.call_args_list]
        assert rounds == [1, 1]

    def test_a_veto_sends_the_findings_it_raised_to_the_implementation_that_has_to_fix_them(self) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing(raised))

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (raised,)

    def test_a_pass_whose_findings_are_all_low_severity_delivers_without_asking_the_implementer_again(self) -> None:
        accepted = FindingMother.low_severity()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.approving_with_accepted_debt(accepted)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert conductor.deliver.execute.call_count == 1

    def test_a_pass_whose_findings_are_all_low_severity_puts_them_in_front_of_whoever_reviews_the_pull_request(
        self,
    ) -> None:
        accepted = FindingMother.low_severity()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.approving_with_accepted_debt(accepted)

        conductor.conduct()

        assert conductor.pull_request.body.call_args.kwargs["findings"] == (accepted,)

    def test_the_durable_row_keeps_the_findings_of_every_round_because_one_caught_and_fixed_still_happened(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing(raised))
        conductor.seed_verdict(round=2, verdict=VerdictMother.passing())

        conductor.conduct()

        assert conductor.metrics.record.call_args.args[0].findings == (raised,)

    def test_the_durable_row_keeps_the_findings_of_the_last_round_apart_so_a_pass_with_one_is_never_ambiguous(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing(raised))
        conductor.seed_verdict(round=2, verdict=VerdictMother.passing())

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.findings == (raised,)
        assert recorded.findings_of_the_last_round == ()

    def test_a_second_round_is_sent_only_what_the_last_verdict_raised_because_the_earlier_ones_may_be_fixed(
        self,
    ) -> None:
        first = FindingMother.without_line()
        second = FindingMother.without_line(path="src/y.py")
        conductor = self._conductor(budgets=Budgets(verify_retries=2))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(first)),
            VerificationMother.vetoing(VerdictMother.failing(second)),
            VerificationMother.passing(),
        ]
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing(first))
        conductor.seed_verdict(round=2, verdict=VerdictMother.failing(second))
        conductor.seed_verdict(round=3, verdict=VerdictMother.passing())

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (second,)
        assert conductor.metrics.record.call_args.args[0].findings == (first, second)

    def test_a_veto_with_no_budget_left_closes_the_run_as_blocked_by_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(verify_retries=0))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing())
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing())

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.JUDGE)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_JUDGE
        )
        assert conductor.metrics.record.call_args.args[0].findings == VerdictMother.failing().findings

    def test_a_discarded_verdict_spends_no_verify_retry_and_still_counts_what_the_call_cost(self) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.incoherent_verdict(), VerificationMother.passing()]
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_DISCARDED_VERDICT,
            spend=HarnessSpendMother.of_a_call_that_cost_nothing(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert (recorded.run.verify_discards, recorded.run.verify_retries) == (1, 0)
        assert recorded.spend == HarnessSpend.summing(
            (
                HarnessSpendMother.of_a_call_that_cost_nothing(),
                HarnessSpendMother.of_the_implementer_call(),
                HarnessSpendMother.of_the_judge_call(),
            )
        )
        assert recorded.run.discarded_call.cause is DiscardCause.INCOHERENT_VERDICT

    def test_a_call_that_left_no_verdict_at_all_is_discarded_as_a_failed_call_and_not_as_an_incoherent_one(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.denied_read(), VerificationMother.passing()]

        conductor.conduct()

        assert conductor.metrics.record.call_args.args[0].run.discarded_call.cause is DiscardCause.FAILED_CALL


class TestConductSliceWhenTheImplementerMovedNothing:
    @staticmethod
    def _conductor() -> Conductor:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging()), budgets=Budgets(verify_retries=2)
        )
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(FindingMother.without_line())),
            UnchangedDiffError("the implementer left the diff untouched"),
        ]
        conductor.seed_verdict(round=1, verdict=VerdictMother.failing(FindingMother.without_line()))

        return conductor

    def test_the_first_verification_of_an_invocation_has_nothing_to_compare_with_and_the_next_one_compares(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        compares = [
            call.args[0].compares_with_the_last_verification for call in conductor.verify.execute.call_args_list
        ]
        assert compares == [False, True]

    def test_the_run_closes_with_a_state_of_its_own_instead_of_asking_the_implementer_again(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.JUDGE)
        assert conductor.implement.execute.call_count == 1

    def test_the_issue_is_labelled_with_a_label_of_its_own_and_not_the_one_of_a_veto(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_JUDGE,
        )

    def test_the_round_that_was_not_judged_is_not_counted_as_a_verify_round_nor_as_a_retry(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        run = conductor.closed.run
        assert (run.verify_rounds_logged, run.verify_retries) == (1, 1)

    def test_the_closure_publishes_what_the_judge_still_demands_and_what_the_implementer_declared_left_out(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.seed_debt(left_out=("el cableado del subcomando queda para otra slice",))

        conductor.conduct()

        publication = conductor.repository.publish_findings.call_args.kwargs
        assert publication["history"].last_round == 1
        assert publication["debt"].left_out == ("el cableado del subcomando queda para otra slice",)


class TestConductSliceWhenTheCostOfTheSliceRunsOut:
    def test_discard_after_discard_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.1))
        conductor.verify.execute.side_effect = [
            RejectionMother.incoherent_verdict(),
            RejectionMother.incoherent_verdict(),
        ]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert result.closure == Closure.because_of(ClosingReason.BUDGET)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.ABORTED_BUDGET
        )
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.closure == Closure.because_of(ClosingReason.BUDGET)
        assert recorded.run.discarded_call is not None
        assert recorded.run.discarded_call.step is Step.VERIFY
        assert recorded.run.discarded_call.cause is DiscardCause.INCOHERENT_VERDICT
        assert recorded.run.verify_rounds_logged == 0

    def test_discard_after_discard_of_the_implementation_closes_the_run_and_writes_its_label(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(slice_cost_usd=0.5)
        )
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            RejectionMother.invalid_implementation_report(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 2
        assert result.closure == Closure.because_of(ClosingReason.BUDGET)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.ABORTED_BUDGET
        )
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.closure == Closure.because_of(ClosingReason.BUDGET)
        assert recorded.run.discarded_call is not None
        assert recorded.run.discarded_call.step is Step.IMPLEMENT
        assert recorded.run.discarded_call.cause is DiscardCause.FAILED_CALL

    def test_a_discard_with_cost_left_asks_the_judge_again_instead_of_closing(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.2))
        conductor.verify.execute.side_effect = [RejectionMother.incoherent_verdict(), VerificationMother.passing()]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert result.closure == Closure.merged()

    def test_a_veto_that_exhausts_the_budget_still_counts_the_round_whose_row_was_already_written(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing())

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.BUDGET)
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.run.verify_rounds_logged == 1

    def test_a_call_the_harness_never_measured_closes_the_run_instead_of_spinning_for_a_cost_nobody_can_add_up(
        self,
    ) -> None:
        conductor = self._judging(budgets=Budgets())
        conductor.verify.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            VerificationMother.passing(),
        ]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.UNMEASURED_CALL)
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.run.discarded_call.step is Step.VERIFY
        assert recorded.run.discarded_call.cause is DiscardCause.FAILED_CALL

    def test_a_call_with_no_measurement_closes_the_run_even_after_an_earlier_call_of_the_run_was_measured(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets())
        conductor.verify.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            RejectionMother.envelope_nobody_could_parse(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert conductor.verify.execute.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.UNMEASURED_CALL)

    def test_an_unmeasured_implementation_call_closes_the_run_instead_of_spinning_for_a_cost_nobody_can_add_up(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets())
        conductor.implement.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            ImplementationMother.of_two_paths(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.UNMEASURED_CALL)

    def test_an_implementation_that_spent_the_whole_cost_closes_before_running_a_single_control(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()),
            budgets=Budgets(slice_cost_usd=0.1),
        )

        result = conductor.conduct()

        assert (conductor.stage.execute.call_count, conductor.controls.run.call_count) == (0, 0)
        assert result.closure == Closure.because_of(ClosingReason.BUDGET)

    def test_a_step_that_never_called_the_harness_is_not_measured_against_the_cost_of_the_slice(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()), budgets=Budgets(slice_cost_usd=0.1)
        )

        result = conductor.conduct()

        assert result.closure == Closure.merged()

    def test_a_pass_that_alone_exceeds_the_cost_still_merges_because_it_was_already_paid_for(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01))
        conductor.verify.execute.return_value = VerificationMother.passing()

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.closure == Closure.merged()

    def test_a_pass_with_accepted_debt_still_delivers_over_budget_because_delivering_costs_no_harness(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01))
        conductor.verify.execute.return_value = VerificationMother.approving_with_accepted_debt(
            FindingMother.low_severity()
        )

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.closure == Closure.merged()

    def test_the_cost_of_an_over_budget_pass_still_blocks_the_next_call_the_harness_would_make(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01, ci_retries=1))
        conductor.verify.execute.return_value = VerificationMother.passing()
        conductor.ci.status.return_value = CiStatus.RED

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.closure == Closure.because_of(ClosingReason.BUDGET)

    @staticmethod
    def _judging(*, budgets: Budgets) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()), budgets=budgets)


class TestConductSliceWhenThePullRequestWasClosedWithoutMerging:
    @staticmethod
    def _conductor() -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        return conductor

    def test_the_invocation_ends_instead_of_ticking_for_a_merge_that_can_no_longer_arrive(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert result.halt is Halt.PULL_REQUEST_CLOSED
        assert conductor.clock.sleep.call_count == 0
        assert conductor.forum.pull_request_state.call_count == 1

    def test_the_run_is_left_open_on_its_step_and_no_durable_row_is_written_because_it_did_not_close(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert (result.halt, result.closure, result.step, result.pull_request) == (
            Halt.PULL_REQUEST_CLOSED,
            Closure.open(),
            Step.AWAIT_MERGE,
            Conductor.PULL_REQUEST,
        )
        assert conductor.metrics.record.call_count == 0


class TestConductSliceWhenAReviewAsksForAChangeOnThePullRequest:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None, run: Run | None = None) -> Conductor:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(run or RunMother.awaiting_merge()),
            budgets=budgets or Budgets(person_wait_seconds=30),
        )
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        return conductor

    def test_a_submitted_review_sends_the_slice_back_to_implement_instead_of_waiting_for_the_merge(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1

    def test_the_body_and_every_line_comment_of_the_review_travel_together_in_the_order_they_were_written(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change_with_a_body_and_several_comments(
                body="corrige el manejo de errores", asked="esta linea sobra", also="y de paso mira el nombre"
            ),
        )

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(
                body="corrige el manejo de errores",
                comments=(
                    PullRequestReviewCommentMother.anchored_to_a_line(body="esta linea sobra"),
                    PullRequestReviewCommentMother.anchored_to_a_line(body="y de paso mira el nombre", line=43),
                ),
            ),
        )

    def test_the_native_request_changes_gesture_asks_for_a_change_too_when_a_teammate_can_use_it(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (
            PullRequestReviewMother.requesting_changes(asked="usa el value object"),
        )

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="usa el value object"),
        )

    @pytest.mark.parametrize(
        "review",
        [
            PullRequestReviewMother.approving(),
            PullRequestReviewMother.still_a_draft(),
            PullRequestReviewMother.dismissed(),
        ],
    )
    def test_a_review_that_neither_approves_nor_is_submitted_never_sends_the_slice_back_to_implement(
        self, review: PullRequestReview
    ) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (review,)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0

    def test_the_judge_is_never_invoked_to_deliver_a_correction_that_only_answers_a_review(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.verify.execute.call_count == 0

    def test_the_correction_spends_neither_the_judge_nor_the_ci_retry_budget(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written
        assert all((run.verify_retries, run.ci_retries) == (0, 0) for run in written)

    def test_several_changes_requested_reviews_are_delivered_in_a_single_round_in_the_order_they_were_sent(
        self,
    ) -> None:
        first = PullRequestReviewMother.asking_for_a_change(review_id=101, asked="arregla A")
        second = PullRequestReviewMother.asking_for_a_change(review_id=102, asked="arregla B")
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (first, second)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="arregla A"),
            RequestedChange(body="arregla B"),
        )

    def test_the_body_of_the_review_reaches_the_implementer_in_the_round_it_triggers(self) -> None:
        asked = "usa el value object en vez del dict"
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(asked=asked),)

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (RequestedChange(body=asked),)

    def test_reinvoking_after_the_marker_advanced_does_not_reprocess_the_same_review(self) -> None:
        conductor = self._conductor(run=RunMother.awaiting_merge_after_reviewing(101))
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(review_id=101),)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0

    def test_the_marker_is_remembered_across_invocations_so_a_later_invocation_does_not_repeat_it(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(review_id=101),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert any(run.last_reviewed_id == 101 for run in written)

    def test_the_correction_delivers_again_reusing_the_pull_request_already_open_for_the_slice(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.deliver.execute.call_count == 1
        assert conductor.deliver.execute.call_args.args[0].branch == _BRANCH

    def test_the_text_of_the_review_is_persisted_with_its_marker_so_a_dead_invocation_does_not_swallow_it(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(asked="arregla el borde"),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert (RequestedChange(body="arregla el borde"),) in [run.requested_changes for run in written]

    def test_an_invocation_resumed_mid_correction_reaches_the_implementer_with_the_review_it_had_to_attend(
        self,
    ) -> None:
        conductor = self._conductor(run=RunMother.correcting_a_review("arregla el borde"))

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="arregla el borde"),
        )

    def test_an_invocation_resumed_mid_correction_still_carries_the_anchored_comments_file_and_line(self) -> None:
        conductor = self._conductor(run=RunMother.correcting_a_review_with_an_anchored_comment())

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(),)),
        )

    def test_delivering_the_correction_clears_the_review_so_the_next_round_is_judged_again(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        delivered = [
            call.kwargs["run"]
            for call in conductor.repository.write_run.call_args_list
            if call.kwargs["run"].step is Step.OPEN_PULL_REQUEST
        ]
        assert delivered
        assert all(run.requested_changes == () for run in delivered)


class TestConductSliceWaitingForTheMerge:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()), budgets=budgets)

    def test_a_merge_that_never_arrives_flags_the_subissue_that_its_pull_request_was_left_unmerged(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert result.halt is Halt.WAIT_EXHAUSTED
        conductor.repository.flag_unmerged_pull_request.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, pull_request=Conductor.PULL_REQUEST
        )

    def test_a_ci_wait_that_is_exhausted_flags_nothing_because_the_pull_request_is_not_awaiting_a_merge_yet(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(ci_wait_seconds=30),
        )
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.flag_unmerged_pull_request.call_count == 0


class TestConductSliceWaitingForTheCi(_ResumedAwaitingTheCi):
    def test_a_pending_ci_ticks_with_the_separation_the_budget_declares_until_the_total_wait_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=90))
        conductor.ci.status.return_value = CiStatus.PENDING

        result = conductor.conduct()

        assert [call.kwargs["seconds"] for call in conductor.clock.sleep.call_args_list] == [30, 30, 30]
        assert (result.halt, result.closure, result.step) == (Halt.WAIT_EXHAUSTED, Closure.open(), Step.AWAIT_CI)

    def test_a_hung_ci_runs_out_on_its_own_cap_however_long_a_person_is_allowed_to_take(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60, person_wait_seconds=86400))
        conductor.ci.status.return_value = CiStatus.PENDING

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == 2
        assert (result.halt, result.step) == (Halt.WAIT_EXHAUSTED, Step.AWAIT_CI)

    def test_what_the_ci_took_is_not_charged_to_the_person_who_has_to_merge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60, person_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.PENDING, CiStatus.GREEN]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == 3
        assert (result.halt, result.step) == (Halt.WAIT_EXHAUSTED, Step.AWAIT_MERGE)

    def test_a_tick_that_changes_nothing_does_not_rewrite_the_state_of_the_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.write_run.call_count == 0

    def test_an_invocation_that_ends_without_closing_the_run_writes_no_durable_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0

    def test_a_resumed_run_finds_the_pull_request_of_its_branch_whatever_state_it_is_already_in(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.forum.any_pull_request.assert_called_with(repo=Conductor.REPO, branch=_BRANCH)
        assert conductor.forum.open_pull_request.call_count == 0
        assert conductor.ci.status.call_args.kwargs["pull_request"] == Conductor.PULL_REQUEST

    def test_a_resumed_run_whose_branch_never_had_a_pull_request_raises_instead_of_asking_about_nothing(self) -> None:
        conductor = self._conductor()
        conductor.forum.any_pull_request.return_value = None

        with pytest.raises(NoPullRequestError, match=_BRANCH):
            conductor.conduct()

    def test_a_ci_with_no_checks_closes_the_run_only_after_the_whole_grace_window(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == Budgets().indeterminate_ticks - 1
        assert result.closure == Closure.because_of(ClosingReason.CI_INDETERMINATE)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_CI_INDETERMINATE,
        )

    def test_a_conflicting_pull_request_with_no_checks_spends_its_own_retry_budget_not_the_indeterminate_window(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == Budgets().catch_up_retries
        assert result.closure == Closure.because_of(ClosingReason.CI_CONFLICT)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_CI_CONFLICT,
        )

    def test_a_conflicting_pull_request_that_closes_is_left_open_because_the_fix_is_merging_the_base(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.close.execute.call_count == 0

    def test_a_mergeable_pull_request_with_no_checks_still_spends_the_whole_grace_window(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == Budgets().indeterminate_ticks - 1
        assert result.closure == Closure.because_of(ClosingReason.CI_INDETERMINATE)

    def test_a_ci_state_nobody_can_read_counts_as_indeterminate_and_not_as_a_failure_of_the_slice(self) -> None:
        conductor = self._conductor(budgets=Budgets(indeterminate_ticks=1))
        conductor.ci.status.return_value = CiStatus.UNKNOWN

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.closure == Closure.because_of(ClosingReason.CI_INDETERMINATE)

    def test_a_red_ci_sends_the_slice_back_to_be_implemented_and_closes_when_that_budget_runs_out(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.RED

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.closure == Closure.because_of(ClosingReason.CI_RED)
        assert conductor.metrics.record.call_args.args[0].closure == Closure.because_of(ClosingReason.CI_RED)


class TestConductSliceReusesTheSamePullRequestStatusReadForTheCiAndTheMerge(_ResumedAwaitingTheCi):
    def test_a_green_ci_asks_about_the_pull_request_only_once_to_poll_the_merge_and_not_to_check_a_conflict(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.GREEN

        conductor.conduct()

        assert conductor.forum.pull_request_state.call_count == 1


class TestConductSliceWhenTheCiCannotBeRead:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(indeterminate_ticks=0),
        )

    def test_the_command_itself_failing_still_closes_as_indeterminate_and_not_as_a_crash(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")

        result = conductor.conduct()

        assert result.closure == Closure.because_of(ClosingReason.CI_INDETERMINATE)

    def test_the_command_itself_failing_records_that_concrete_cause_on_the_durable_row(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED

    def test_a_response_that_arrived_but_could_not_be_read_records_a_different_cause_than_a_failed_command(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = UnreadableCiError("gh did not return JSON: not valid")

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.UNREADABLE_RESPONSE

    def test_a_legitimate_no_checks_reading_leaves_the_cause_out_because_nothing_failed(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is None

    def test_a_failed_command_against_a_conflicting_pull_request_records_no_indeterminate_cause(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is None

    def test_a_cause_recorded_on_an_earlier_tick_survives_a_later_tick_that_reads_the_ci_cleanly(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()))
        conductor.ci.status.side_effect = [
            CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited"),
            CiStatus.GREEN,
        ]

        result = conductor.conduct()

        assert result.closure == Closure.merged()
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED


class TestConductSliceMountingTheWorktreeBeforeUnderstanding:
    _MANUAL = "/trees/by-hand"

    @staticmethod
    def _conductor() -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(),)
        conductor.worktrees.branch_exists.return_value = False

        return conductor

    def test_a_new_run_mounts_the_worktree_that_hangs_from_the_root_and_the_identity_of_the_slice(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.worktrees.add_new_branch.assert_called_once_with(
            root=Conductor.ROOT, path=Conductor.WORKTREE, branch=_BRANCH, base=Conductor.BASE
        )
        assert Conductor.WORKTREE == f"{Conductor.ROOT}/.worktrees/05-prechecks-deterministas"

    def test_the_derived_path_hangs_from_the_root_through_a_first_directory_that_starts_with_a_dot(self) -> None:
        relative = Path(Conductor.WORKTREE).relative_to(Conductor.ROOT)

        assert relative.parts[0].startswith(".")
        assert Path(Conductor.WORKTREE).name == _BRANCH.removeprefix("slice/")

    def test_a_new_run_ignores_the_directory_of_the_worktrees_in_the_clone(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.worktrees.exclude.assert_any_call(root=Conductor.ROOT, rule="/.worktrees/")
        assert conductor.worktrees.exclude.call_count == 2

    def test_the_sources_are_read_from_the_freshly_mounted_worktree_and_not_from_the_root(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        params = conductor.check_sources.execute.call_args.args[0]
        assert params.worktree == Conductor.WORKTREE
        assert params.worktree != Conductor.ROOT

    def test_the_precheck_of_the_base_is_asked_from_the_root_of_the_clone(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.prechecks.execute.call_args.args[0].root == Conductor.ROOT

    def test_a_branch_taken_by_another_worktree_closes_the_run_in_the_state_that_names_the_worktree(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=self._MANUAL, branch=_BRANCH),
        )

        result = conductor.conduct()

        assert (result.halt, result.closure) == (Halt.RUN_CLOSED, Closure.because_of(ClosingReason.WORKTREE))
        assert result.conflicting_path == self._MANUAL
        assert conductor.metrics.record.call_args.args[0].closure == Closure.because_of(ClosingReason.WORKTREE)

    def test_a_taken_branch_labels_the_subissue_and_reads_no_sources_nor_asks_the_harness(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=self._MANUAL, branch=_BRANCH),
        )

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.PENDING, add=IssueLabel.BLOCKED_WORKTREE
        )
        assert conductor.check_sources.execute.call_count == 0

    def test_a_run_closed_before_it_started_persists_the_step_it_stands_on_so_that_a_retry_can_reopen_it(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=self._MANUAL, branch=_BRANCH),
        )

        conductor.conduct()

        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, run=Run(step=Step.MOUNT_WORKTREE)
        )

    def test_sources_that_cannot_be_read_after_mounting_end_the_invocation_and_leave_the_worktree_for_the_next(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.check_sources.execute.return_value = PrecheckResult(
            outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md does not exist under the worktree"
        )

        first = conductor.conduct()
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=Conductor.WORKTREE, branch=_BRANCH),
        )
        conductor.worktrees.branch_exists.return_value = True
        conductor.check_sources.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.CLEAR)
        conductor.conduct()

        assert (first.halt, first.precheck) == (
            Halt.PRECHECKS_BLOCKED,
            PrecheckResult(
                outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md does not exist under the worktree"
            ),
        )
        conductor.worktrees.add_new_branch.assert_called_once()
        conductor.worktrees.add_on_branch.assert_not_called()
        conductor.repository.write_precheck_reason.assert_called_once()

    def test_a_worktree_given_by_hand_wins_over_deriving_one(self) -> None:
        conductor = self._conductor()

        conductor.conduct(worktree=self._MANUAL)

        conductor.worktrees.add_new_branch.assert_called_once_with(
            root=Conductor.ROOT, path=self._MANUAL, branch=_BRANCH, base=Conductor.BASE
        )
        assert conductor.check_sources.execute.call_args.args[0].worktree == self._MANUAL

    def test_a_tree_by_hand_that_belongs_to_another_clone_than_the_root_mounts_nothing_and_closes(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.common_dir.side_effect = lambda *, path: (
            "/other/clone/.git" if path == self._MANUAL else Conductor.COMMON_DIR
        )

        result = conductor.conduct(worktree=self._MANUAL)

        assert result.closure == Closure.because_of(ClosingReason.WORKTREE)
        assert not conductor.worktrees.add_new_branch.called
        assert not conductor.worktrees.add_on_branch.called
        assert not conductor.worktrees.prune.called

    def test_a_tree_by_hand_in_another_location_on_the_derived_branch_is_the_one_of_this_slice(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=self._MANUAL, branch=_BRANCH),
        )

        result = conductor.conduct(worktree=self._MANUAL)

        assert result.closure != Closure.because_of(ClosingReason.WORKTREE)
        assert not conductor.worktrees.add_new_branch.called
        assert conductor.check_sources.execute.call_args.args[0].worktree == self._MANUAL

    def test_a_tree_by_hand_on_a_foreign_branch_closes_the_run(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path=self._MANUAL, branch="slice/00-other"),
        )

        result = conductor.conduct(worktree=self._MANUAL)

        assert (result.closure, result.conflicting_path) == (Closure.because_of(ClosingReason.WORKTREE), self._MANUAL)


class TestConductSliceResumingMountsTheWorktreeFirst:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))

    def test_a_worktree_already_on_its_branch_is_left_as_it_is_and_the_run_goes_on(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.worktrees.exclude.call_count == 2
        assert not conductor.worktrees.add_new_branch.called
        assert not conductor.worktrees.add_on_branch.called
        assert conductor.implement.execute.call_count == 1

    def test_a_branch_that_is_gone_is_created_again_instead_of_stopping_the_run(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.listed.return_value = (ListedWorktreeMother.main_clone(),)
        conductor.worktrees.branch_exists.return_value = False

        conductor.conduct()

        conductor.worktrees.add_new_branch.assert_called_once()
        assert conductor.implement.execute.call_count == 1

    def test_a_worktree_whose_directory_was_deleted_by_hand_is_pruned_and_mounted_again(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.whose_directory_was_deleted(path=Conductor.WORKTREE, branch=_BRANCH),
        )

        conductor.conduct()

        conductor.worktrees.prune.assert_called_once_with(root=Conductor.ROOT)
        conductor.worktrees.add_on_branch.assert_called_once()

    def test_a_branch_taken_elsewhere_closes_the_run_from_whatever_step_it_stood_on(self) -> None:
        conductor = self._conductor()
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path="/trees/by-hand", branch=_BRANCH),
        )

        result = conductor.conduct()

        assert (result.closure, result.step) == (Closure.because_of(ClosingReason.WORKTREE), Step.IMPLEMENT)
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_WORKTREE
        )
        assert conductor.implement.execute.call_count == 0

    def test_a_run_closed_on_the_worktree_before_it_ever_started_resumes_by_reading_the_sources_and_implementing(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(Run(step=Step.MOUNT_WORKTREE)))

        conductor.conduct()

        assert conductor.check_sources.execute.call_count == 1
        assert conductor.implement.execute.call_count == 1


class TestConductSliceLeavingAnEventWhenItStarts:
    @staticmethod
    def _starting() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start())

    def test_a_new_run_reports_implement_advancing_with_no_spend_before_the_implementer_is_asked(self) -> None:
        conductor = self._starting()
        emitted_when_asked: list[int] = []

        def implementing(params: object) -> Implementation:
            emitted_when_asked.append(len(conductor.emitted_events))

            return ImplementationMother.of_two_paths()

        conductor.implement.execute.side_effect = implementing

        conductor.conduct()

        first = conductor.emitted_events[0]
        assert (first.step, first.closure, first.spend) == (
            Step.IMPLEMENT,
            Closure.open(),
            HarnessSpend.nothing(),
        )
        assert emitted_when_asked == [1]

    def test_the_start_event_names_the_parent_issue_of_the_feature_and_the_name_of_the_slice(self) -> None:
        conductor = self._starting()

        conductor.conduct()

        expected = FeatureSlice(parent=Conductor.ISSUE, name=SubIssueMother.pending().slice_id.name)
        assert conductor.emitted_events[0].feature_slice == expected

    def test_a_run_resumed_awaiting_the_merge_leaves_its_first_transition_as_the_first_event(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        assert [e.closure for e in conductor.emitted_events] == [Closure.merged()]

    def test_a_run_resumed_awaiting_the_ci_leaves_its_first_transition_as_the_first_event(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_ci()))

        conductor.conduct()

        assert conductor.emitted_events[0].step is Step.AWAIT_MERGE

    def test_an_invocation_stopped_by_the_precheck_leaves_no_start_event(self) -> None:
        conductor = self._starting()
        conductor.prechecks.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN)

        conductor.conduct()

        assert conductor.emitted_events == []

    def test_an_invocation_stopped_by_an_unreadable_source_leaves_no_start_event(self) -> None:
        conductor = self._starting()
        conductor.check_sources.execute.return_value = PrecheckResult(
            outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md does not exist under the worktree"
        )

        conductor.conduct()

        assert conductor.emitted_events == []

    def test_an_invocation_closed_by_a_busy_worktree_leaves_no_start_event(self) -> None:
        conductor = self._starting()
        conductor.worktrees.branch_exists.return_value = True
        conductor.worktrees.listed.return_value = (
            ListedWorktreeMother.main_clone(),
            ListedWorktreeMother.mounted(path="/repos/manual-worktree", branch=_BRANCH),
        )

        conductor.conduct()

        assert [e.closure for e in conductor.emitted_events] == [Closure.because_of(ClosingReason.WORKTREE)]
