from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.requested_change import RequestedChange
from slice_runner.domain.run import Run
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother

if TYPE_CHECKING:
    from slice_runner.domain.discarded_call import DiscardedCall
    from slice_runner.domain.harness_spend import HarnessSpend


class RunMother:
    @staticmethod
    def blocked_on_the_worktree() -> Run:
        return Run(step=Step.IMPLEMENT, control_retries=1, verify_retries=1)

    @staticmethod
    def aborted_before_touching_code() -> Run:
        return Run(step=Step.UNDERSTAND)

    @staticmethod
    def implementing() -> Run:
        return Run(step=Step.IMPLEMENT)

    @staticmethod
    def implementing_with_one_round_already_logged() -> Run:
        return Run(step=Step.IMPLEMENT, control_rounds_logged=1)

    @staticmethod
    def implementing_after_a_dead_call() -> Run:
        return Run(step=Step.IMPLEMENT, previous_call_died=True)

    @staticmethod
    def judging_after_spending(spend: HarnessSpend) -> Run:
        return Run(step=Step.VERIFY, spend=spend)

    @staticmethod
    def running_the_controls() -> Run:
        return Run(step=Step.RUN_CONTROLS)

    @staticmethod
    def running_the_controls_with_one_round_already_logged() -> Run:
        return Run(step=Step.RUN_CONTROLS, control_rounds_logged=1)

    @staticmethod
    def judging() -> Run:
        return Run(step=Step.VERIFY)

    @staticmethod
    def judging_after_one_control_round() -> Run:
        return Run(step=Step.VERIFY, control_rounds_logged=1)

    @staticmethod
    def about_to_open_the_pull_request() -> Run:
        return Run(step=Step.OPEN_PULL_REQUEST, control_rounds_logged=1)

    @staticmethod
    def about_to_ask_the_ci_after_one_control_round() -> Run:
        return Run(step=Step.AWAIT_CI, control_rounds_logged=1)

    @staticmethod
    def judging_with_one_verify_round_already_logged() -> Run:
        return Run(step=Step.VERIFY, verify_rounds_logged=1)

    @staticmethod
    def about_to_ask_the_ci() -> Run:
        return Run(step=Step.AWAIT_CI)

    @staticmethod
    def awaiting_ci() -> Run:
        return Run(step=Step.AWAIT_CI, control_retries=1, indeterminate_ticks=2)

    @staticmethod
    def with_the_only_ci_retry_already_spent() -> Run:
        return Run(step=Step.AWAIT_CI, ci_retries=1)

    @staticmethod
    def with_one_catch_up_retry_already_spent() -> Run:
        return Run(step=Step.AWAIT_CI, catch_up_retries=1)

    @staticmethod
    def awaiting_merge() -> Run:
        return Run(step=Step.AWAIT_MERGE)

    @staticmethod
    def awaiting_merge_after_discarding(discarded: DiscardedCall) -> Run:
        return Run(step=Step.AWAIT_MERGE, discarded_call=discarded)

    @staticmethod
    def awaiting_merge_after_reviewing(review_id: int) -> Run:
        return Run(step=Step.AWAIT_MERGE, last_reviewed_id=review_id)

    @staticmethod
    def correcting_a_review(text: str) -> Run:
        return Run(step=Step.IMPLEMENT, last_reviewed_id=101, requested_changes=(RequestedChange(body=text),))

    @staticmethod
    def correcting_a_review_with_an_anchored_comment() -> Run:
        return Run(
            step=Step.IMPLEMENT,
            last_reviewed_id=101,
            requested_changes=(
                RequestedChange(body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(),)),
            ),
        )

    @staticmethod
    def implementing_after_a_retry(instruction: str) -> Run:
        return Run(step=Step.IMPLEMENT, retry_instruction=instruction)

    @staticmethod
    def blocked_on_controls() -> Run:
        return Run(step=Step.RUN_CONTROLS, control_retries=2, control_rounds_logged=3)

    @staticmethod
    def blocked_on_controls_while_catching_up_the_branch() -> Run:
        return Run(step=Step.RUN_CONTROLS, control_retries=2, control_rounds_logged=3, catching_up_the_branch=True)

    @staticmethod
    def blocked_on_verify() -> Run:
        return Run(step=Step.VERIFY, verify_retries=2)

    @staticmethod
    def blocked_on_red_ci() -> Run:
        return Run(step=Step.AWAIT_CI, ci_retries=1)

    @staticmethod
    def blocked_on_indeterminate_ci() -> Run:
        return Run(step=Step.AWAIT_CI, indeterminate_ticks=3)

    @staticmethod
    def blocked_on_conflict() -> Run:
        return Run(step=Step.AWAIT_CI, catch_up_retries=3)

    @staticmethod
    def blocked_on_conflict_with_indeterminate_ticks_piled_up() -> Run:
        return Run(step=Step.AWAIT_CI, catch_up_retries=3, indeterminate_ticks=8)

    @staticmethod
    def aborted_for_budget(spend: HarnessSpend) -> Run:
        return Run(step=Step.VERIFY, spend=spend)

    @staticmethod
    def aborted_for_an_unmeasured_call(spend: HarnessSpend) -> Run:
        return Run(step=Step.VERIFY, spend=spend)

    @staticmethod
    def merged_after_retrying_controls_and_ci(*, control_retries: int, ci_retries: int) -> Run:
        return Run(step=Step.AWAIT_MERGE, control_retries=control_retries, ci_retries=ci_retries)

    @staticmethod
    def that_went_back_for_every_reason() -> Run:
        return Run(
            step=Step.AWAIT_MERGE,
            control_retries=1,
            hygiene_retries=5,
            verify_retries=2,
            ci_retries=3,
            verify_discards=4,
        )
