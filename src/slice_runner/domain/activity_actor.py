from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.step import Step


class ActivityActor(StrEnum):
    IMPLEMENTER = "implementer"
    JUDGE = "judge"
    CONTROLS = "controls"

    @classmethod
    def of_the_harness_call_at(cls, step: Step) -> ActivityActor:
        match step:
            case Step.IMPLEMENT:
                return cls.IMPLEMENTER
            case Step.VERIFY:
                return cls.JUDGE
            case (
                Step.MOUNT_WORKTREE
                | Step.UNDERSTAND
                | Step.RUN_CONTROLS
                | Step.OPEN_PULL_REQUEST
                | Step.AWAIT_CI
                | Step.CATCH_UP
                | Step.AWAIT_MERGE
            ):
                raise ValueError(f"no harness call is made at the `{step}` step")
