from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from slice_runner.domain.halt import Halt
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.closure import Closure


class ExitCode(IntEnum):
    OK = 0
    VETOED = 1
    NO_USABLE_VERDICT = 2
    NO_DIFF = 3
    USAGE_ERROR = 4
    RUN_UNMERGED = 5
    WAIT_EXHAUSTED = 7
    PRECHECKS_BLOCKED = 8
    NO_SLICE_LEFT = 9
    RUN_INTERRUPTED = 10
    PULL_REQUEST_CLOSED = 11
    PROCESS_TIMED_OUT = 12
    ENVIRONMENT_NOT_READY = 13
    SOURCES_BUDGET_EXCEEDED = 14
    UNCHANGED_DIFF = 15
    ORDER_REFUSED = 18
    TUI_NOT_INSTALLED = 19
    LIVE_RUNS = 20
    UNSUPPORTED_PLATFORM = 21
    RELEASE_INCOMPLETE = 22

    @classmethod
    def of(cls, ruling: Ruling) -> ExitCode:
        match ruling:
            case Ruling.PASS:
                return cls.OK
            case Ruling.FAIL:
                return cls.VETOED

    @classmethod
    def of_the_halt(cls, *, halt: Halt, closure: Closure) -> ExitCode:
        match halt:
            case Halt.RUN_CLOSED:
                return cls._of_the_closing(closure)
            case Halt.PRECHECKS_BLOCKED:
                return cls.PRECHECKS_BLOCKED
            case Halt.WAIT_EXHAUSTED:
                return cls.WAIT_EXHAUSTED
            case Halt.PULL_REQUEST_CLOSED:
                return cls.PULL_REQUEST_CLOSED

    @classmethod
    def _of_the_closing(cls, closure: Closure) -> ExitCode:
        match closure.state:
            case RunState.MERGED:
                return cls.OK
            case RunState.OPEN | RunState.ABORTED | RunState.BLOCKED:
                return cls.RUN_UNMERGED
