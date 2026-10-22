from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.step import Step


class WaitingOn(StrEnum):
    PERSON = "person"
    MACHINE = "machine"

    @classmethod
    def of_the_step(cls, step: Step) -> WaitingOn:
        match step:
            case Step.UNDERSTAND | Step.AWAIT_MERGE:
                return cls.PERSON
            case (
                Step.MOUNT_WORKTREE
                | Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.AWAIT_CI
                | Step.CATCH_UP
            ):
                return cls.MACHINE
