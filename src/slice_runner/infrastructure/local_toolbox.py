from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.toolbox import Toolbox
from slice_runner.infrastructure.process import ProcessNotRunnableError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class LocalToolbox(Toolbox):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def version_of(self, executable: str) -> str | None:
        try:
            output = self._process.run([executable, "--version"], stdin="")
        except ProcessNotRunnableError:
            return None

        if output.code != 0:
            return None

        return output.stdout.strip()
