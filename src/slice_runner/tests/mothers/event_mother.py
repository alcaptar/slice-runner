from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.event import Event
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.rounds import Rounds
from slice_runner.domain.step import Step
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


class EventMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 150
    ANOTHER_REPO: ClassVar[str] = "alcaptar/another-repo"
    BUDGETS: ClassVar[Budgets] = Budgets()
    PULL_REQUEST: ClassVar[int] = 151
    PID: ClassVar[int] = 48213
    COMPARISON: ClassVar[str] = "/repos/slice-runner/.worktrees/05-follow/.design-captures/comparison.html"

    @classmethod
    def advancing(cls) -> Event:
        return Event(
            slice_id="slice-05",
            repo=cls.REPO,
            issue=cls.ISSUE,
            step=Step.RUN_CONTROLS,
            at=datetime(2024, 1, 1, 12, 30, 45, tzinfo=UTC),
            spend=HarnessSpendMother.of_the_implementer_call(),
            budget_usd=cls.BUDGETS.slice_cost_usd,
            rounds=Rounds.untouched(cls.BUDGETS),
            closure=Closure.open(),
            feature_slice=FeatureSliceMother.of_the_feature(),
        )

    @classmethod
    def pending(cls) -> Event:
        return replace(cls.advancing(), step=None, spend=HarnessSpend.nothing())

    @classmethod
    def closed(cls) -> Event:
        return Event(
            slice_id="slice-05",
            repo=cls.REPO,
            issue=cls.ISSUE,
            step=Step.AWAIT_MERGE,
            at=datetime(2024, 1, 1, 12, 31, 15, tzinfo=UTC),
            spend=HarnessSpendMother.of_the_judge_call(),
            budget_usd=cls.BUDGETS.slice_cost_usd,
            rounds=Rounds.untouched(cls.BUDGETS),
            closure=Closure.merged(),
            feature_slice=FeatureSliceMother.of_the_feature(),
        )

    @classmethod
    def blocked_by_the_judge(cls) -> Event:
        return replace(cls.closed(), closure=Closure.because_of(ClosingReason.JUDGE))

    @classmethod
    def round_without_changes(cls) -> Event:
        return replace(cls.advancing(), round_without_changes=True)

    @classmethod
    def awaiting_merge(cls) -> Event:
        return replace(cls.closed(), closure=Closure.open())

    @classmethod
    def awaiting_merge_of_a_pull_request_from_a_process(cls) -> Event:
        return replace(cls.awaiting_merge(), pull_request=cls.PULL_REQUEST, pid=cls.PID)

    @classmethod
    def awaiting_merge_with_a_comparison_page(cls) -> Event:
        return replace(cls.awaiting_merge_of_a_pull_request_from_a_process(), comparison=cls.COMPARISON)

    @classmethod
    def advancing_before_the_feature_was_recorded(cls) -> Event:
        return replace(cls.advancing(), feature_slice=None)

    @classmethod
    def advancing_again(cls, *, minutes_later: int) -> Event:
        event = cls.advancing()

        return replace(event, at=event.at + timedelta(minutes=minutes_later))

    @classmethod
    def advancing_in_another_slice(cls) -> Event:
        return replace(cls.advancing(), slice_id="slice-06")

    @classmethod
    def advancing_in_another_repo(cls) -> Event:
        return replace(cls.advancing(), repo=cls.ANOTHER_REPO)

    @classmethod
    def waiting_on_a_machine(cls) -> Event:
        return replace(cls.advancing_again(minutes_later=1), step=Step.AWAIT_CI)
