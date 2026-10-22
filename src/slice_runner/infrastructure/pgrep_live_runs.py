from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.live_runs import LiveRuns

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class PgrepLiveRuns(LiveRuns):
    PATTERN: ClassVar[str] = "slice-runner run "

    def __init__(self, *, process: Process) -> None:
        self._process = process

    def command_lines(self) -> tuple[str, ...]:
        output = self._process.run(["pgrep", "-fl", self.PATTERN], stdin="")

        return tuple(line.strip() for line in output.stdout.splitlines() if line.strip())
