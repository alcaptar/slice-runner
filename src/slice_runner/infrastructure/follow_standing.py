from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from slice_runner.domain.closure import Closure
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


class FollowStanding(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    AWAITING_MERGE = "awaiting-merge"
    BLOCKED = "blocked"
    ABORTED = "aborted"
    MERGED = "merged"

    @classmethod
    def of(cls, *, closure: Closure, step: Step | None) -> FollowStanding:
        match closure.state:
            case RunState.OPEN:
                return cls._of_the_open_step(step)
            case RunState.MERGED:
                return cls.MERGED
            case RunState.BLOCKED:
                return cls.BLOCKED
            case RunState.ABORTED:
                return cls.ABORTED

    @classmethod
    def _of_the_open_step(cls, step: Step | None) -> FollowStanding:
        label = IssueLabel.of(closure=Closure.open(), step=step)
        assert label is not None

        return {
            IssueLabel.PENDING: cls.PENDING,
            IssueLabel.IN_PROGRESS: cls.IN_PROGRESS,
            IssueLabel.AWAITING_MERGE: cls.AWAITING_MERGE,
        }[label]
