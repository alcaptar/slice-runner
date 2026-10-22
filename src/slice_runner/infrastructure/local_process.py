from __future__ import annotations

import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import IO

    from slice_runner.domain.budgets import Budgets


class _RunOutcome:
    def __init__(self) -> None:
        self.finished: subprocess.CompletedProcess[str] | None = None
        self.error: subprocess.TimeoutExpired | OSError | None = None


class LocalProcess(Process):
    _POLL_SECONDS: ClassVar[float] = 0.05

    def __init__(self, *, budgets: Budgets, subprocess: ModuleType) -> None:
        self._budgets = budgets
        self._subprocess = subprocess

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        if on_line is None:
            return self._capturing(argv, stdin=stdin, cwd=cwd)

        return self._tailing(argv, stdin=stdin, cwd=cwd, on_line=on_line)

    def _capturing(self, argv: list[str], *, stdin: str, cwd: str | None) -> ProcessOutput:
        try:
            finished = self._subprocess.run(
                argv,
                input=stdin,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                timeout=self._budgets.process_timeout_seconds,
            )
        except subprocess.TimeoutExpired as expired:
            raise ProcessTimedOutError(f"{argv[0]}: killed after {self._budgets.process_timeout_seconds}s") from expired
        except OSError as error:
            raise ProcessNotRunnableError(f"{argv[0]}: {error.strerror or error}") from error

        return ProcessOutput(code=finished.returncode, stdout=finished.stdout, stderr=finished.stderr)

    def _tailing(
        self, argv: list[str], *, stdin: str, cwd: str | None, on_line: Callable[[str], None]
    ) -> ProcessOutput:
        outcome = _RunOutcome()
        with tempfile.TemporaryDirectory() as directory:
            stdout_path = Path(directory) / "stdout"
            with stdout_path.open("w", encoding="utf-8") as sink:
                worker = threading.Thread(target=self._launched, args=(argv, stdin, cwd, sink, outcome))
                worker.start()
                self._tail(stdout_path, worker=worker, on_line=on_line)
                worker.join()

            return self._concluded(argv, outcome, stdout_path=stdout_path)

    def _launched(self, argv: list[str], stdin: str, cwd: str | None, sink: IO[str], outcome: _RunOutcome) -> None:
        try:
            outcome.finished = self._subprocess.run(
                argv,
                input=stdin,
                stdout=sink,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                cwd=cwd,
                timeout=self._budgets.process_timeout_seconds,
            )
        except subprocess.TimeoutExpired as expired:
            outcome.error = expired
        except OSError as error:
            outcome.error = error

    def _tail(self, path: Path, *, worker: threading.Thread, on_line: Callable[[str], None]) -> None:
        emitted = 0
        while worker.is_alive():
            emitted = self._emitted(path, already=emitted, on_line=on_line)
            time.sleep(self._POLL_SECONDS)
        self._emitted(path, already=emitted, on_line=on_line, final=True)

    @staticmethod
    def _emitted(path: Path, *, already: int, on_line: Callable[[str], None], final: bool = False) -> int:
        lines = path.read_text(encoding="utf-8").split("\n")
        complete = lines if final else lines[:-1]
        for line in complete[already:]:
            if line:
                on_line(line)

        return len(complete)

    def _concluded(self, argv: list[str], outcome: _RunOutcome, *, stdout_path: Path) -> ProcessOutput:
        if isinstance(outcome.error, subprocess.TimeoutExpired):
            raise ProcessTimedOutError(
                f"{argv[0]}: killed after {self._budgets.process_timeout_seconds}s"
            ) from outcome.error
        if isinstance(outcome.error, OSError):
            raise ProcessNotRunnableError(f"{argv[0]}: {outcome.error.strerror or outcome.error}") from outcome.error

        finished = outcome.finished
        if finished is None:
            label = argv[0] if argv else str(argv)
            raise ProcessNotRunnableError(f"{label}: the background call left neither a result nor a known error")

        return ProcessOutput(
            code=finished.returncode, stdout=stdout_path.read_text(encoding="utf-8"), stderr=finished.stderr
        )
