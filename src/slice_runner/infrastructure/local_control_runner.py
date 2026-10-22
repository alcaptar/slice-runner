from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.control_outcome import ControlOutcome
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.control_status import ControlStatus
from slice_runner.infrastructure.process import ProcessNotRunnableError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.control_command import ControlCommand
    from slice_runner.infrastructure.process import Process


class LocalControlRunner(ControlRunner):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def run(self, command: ControlCommand, *, worktree: str, out: Path) -> ControlOutcome:
        try:
            output = self._process.run(["sh", "-c", command.command], stdin="", cwd=worktree)
        except ProcessNotRunnableError as unrunnable:
            log = self._logged(command, out=out, text=str(unrunnable))

            return ControlOutcome(status=ControlStatus.UNKNOWN, log=log)

        return ControlOutcome(
            status=ControlStatus.GREEN if output.code == 0 else ControlStatus.RED,
            log=self._logged(command, out=out, text=output.stdout + output.stderr),
        )

    @staticmethod
    def _logged(command: ControlCommand, *, out: Path, text: str) -> Path:
        out.mkdir(parents=True, exist_ok=True)
        log = out / f"{command.name}.log"
        log.write_text(text, encoding="utf-8")

        return log
