from __future__ import annotations

from enum import StrEnum


class Step(StrEnum):
    MOUNT_WORKTREE = "mount-worktree"
    UNDERSTAND = "understand"
    IMPLEMENT = "implement"
    RUN_CONTROLS = "run-controls"
    VERIFY = "verify"
    OPEN_PULL_REQUEST = "open-pull-request"
    AWAIT_CI = "await-ci"
    CATCH_UP = "catch-up"
    AWAIT_MERGE = "await-merge"

    def has_opened_the_pull_request(self) -> bool:
        match self:
            case Step.AWAIT_CI | Step.CATCH_UP | Step.AWAIT_MERGE:
                return True
            case (
                Step.MOUNT_WORKTREE
                | Step.UNDERSTAND
                | Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
            ):
                return False

    def is_after_delivery(self) -> bool:
        match self:
            case Step.AWAIT_CI | Step.AWAIT_MERGE:
                return True
            case (
                Step.MOUNT_WORKTREE
                | Step.UNDERSTAND
                | Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.CATCH_UP
            ):
                return False
