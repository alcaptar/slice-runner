from __future__ import annotations

import errno
import subprocess
import threading
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import create_autospec

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import Mock


class PrintingSubprocess:
    def __init__(
        self,
        *lines: str,
        stderr: str = "",
        code: int = 0,
        after_each: Callable[[str], None] | None = None,
    ) -> None:
        self._lines = lines
        self._stderr = stderr
        self._code = code
        self._after_each = after_each

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        sink = kwargs["stdout"]
        for line in self._lines:
            sink.write(f"{line}\n")
            sink.flush()
            if self._after_each is not None:
                self._after_each(line)

        return subprocess.CompletedProcess(argv, self._code, stdout=None, stderr=self._stderr)


class ALocalProcess:
    ARGV: ClassVar[list[str]] = ["tool", "--flag"]
    CAP_SECONDS: ClassVar[int] = 7

    @staticmethod
    def finishing(*, code: int = 0, stdout: str = "", stderr: str = "") -> Mock:
        module: Mock = create_autospec(subprocess, spec_set=True)
        module.run.side_effect = lambda argv, **_: subprocess.CompletedProcess(argv, code, stdout=stdout, stderr=stderr)

        return module

    @staticmethod
    def printing(command: PrintingSubprocess) -> Mock:
        module: Mock = create_autospec(subprocess, spec_set=True)
        module.run.side_effect = command

        return module

    @staticmethod
    def failing(error: BaseException) -> Mock:
        module: Mock = create_autospec(subprocess, spec_set=True)
        module.run.side_effect = error

        return module

    @classmethod
    def over(cls, module: Mock) -> LocalProcess:
        return LocalProcess(budgets=Budgets(process_timeout_seconds=cls.CAP_SECONDS), subprocess=module)

    @classmethod
    def running(cls, module: Mock, *, watched: bool) -> ProcessOutput:
        on_line: Callable[[str], None] | None = (lambda _: None) if watched else None

        return cls.over(module).run(cls.ARGV, stdin="", on_line=on_line)


class TestACallWithoutAnyoneWatchingItsLines(ALocalProcess):
    def test_it_asks_the_library_for_the_argv_the_stdin_the_cwd_and_the_cap_of_the_budget(self) -> None:
        module = self.finishing(code=0)

        self.over(module).run(self.ARGV, stdin="hello", cwd="/work")

        module.run.assert_called_once_with(
            self.ARGV,
            input="hello",
            capture_output=True,
            text=True,
            check=False,
            cwd="/work",
            timeout=self.CAP_SECONDS,
        )

    def test_a_cwd_that_was_not_asked_for_reaches_the_library_as_none(self) -> None:
        module = self.finishing(code=0)

        self.over(module).run(self.ARGV, stdin="")

        assert module.run.call_args.kwargs["cwd"] is None

    def test_the_exit_code_and_both_streams_come_back_as_data_even_when_the_code_is_not_zero(self) -> None:
        module = self.finishing(code=7, stdout="hello", stderr="oops")

        output = self.over(module).run(self.ARGV, stdin="hello")

        assert (output.code, output.stdout, output.stderr) == (7, "hello", "oops")


class TestAFailureOfTheLibrary(ALocalProcess):
    @pytest.mark.parametrize("watched", [False, True], ids=["without on_line", "with on_line"])
    def test_a_command_that_outlives_the_cap_is_reported_with_the_program_and_that_cap(self, watched: bool) -> None:
        module = self.failing(subprocess.TimeoutExpired(cmd=self.ARGV, timeout=self.CAP_SECONDS))

        with pytest.raises(ProcessTimedOutError) as raised:
            self.running(module, watched=watched)

        assert str(raised.value) == f"tool: killed after {self.CAP_SECONDS}s"

    @pytest.mark.parametrize("watched", [False, True], ids=["without on_line", "with on_line"])
    def test_an_executable_that_cannot_be_launched_is_reported_as_the_environment_failure_it_is(
        self, watched: bool
    ) -> None:
        module = self.failing(OSError(errno.ENOENT, "No such file or directory"))

        with pytest.raises(ProcessNotRunnableError) as raised:
            self.running(module, watched=watched)

        assert str(raised.value) == "tool: No such file or directory"

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_a_launch_that_dies_of_neither_a_timeout_nor_an_os_error_is_reported_as_a_process_failure(self) -> None:
        module = self.failing(ValueError("neither of the two"))

        with pytest.raises(ProcessNotRunnableError, match="left neither a result nor a known error"):
            self.running(module, watched=True)


class TestACallThatWantsEachLineAsItArrives(ALocalProcess):
    LINES = ("one", "two", "three")

    def test_every_line_the_command_prints_reaches_the_callback_in_order(self) -> None:
        seen: list[str] = []

        self.over(self.printing(PrintingSubprocess(*self.LINES))).run(self.ARGV, stdin="", on_line=seen.append)

        assert seen == list(self.LINES)

    def test_the_callback_fires_while_the_command_is_still_running_and_not_only_once_it_exits(self) -> None:
        arrived = threading.Event()
        reached_while_running: list[bool] = []
        command = PrintingSubprocess(
            *self.LINES, after_each=lambda _: reached_while_running.append(arrived.wait(timeout=5))
        )

        self.over(self.printing(command)).run(self.ARGV, stdin="", on_line=lambda _: arrived.set())

        assert reached_while_running[0] is True

    def test_the_full_output_still_comes_back_whole_once_the_command_is_done(self) -> None:
        module = self.printing(PrintingSubprocess(*self.LINES, stderr="oops", code=3))

        output = self.over(module).run(self.ARGV, stdin="", on_line=lambda _: None)

        assert (output.code, output.stdout, output.stderr) == (3, "one\ntwo\nthree\n", "oops")

    def test_the_library_is_asked_for_the_same_cap_and_the_cwd_while_a_callback_is_watching(self) -> None:
        module = self.printing(PrintingSubprocess(*self.LINES))

        self.over(module).run(self.ARGV, stdin="hello", cwd="/work", on_line=lambda _: None)

        call = module.run.call_args
        assert (call.args, call.kwargs["input"], call.kwargs["cwd"], call.kwargs["timeout"], call.kwargs["check"]) == (
            (self.ARGV,),
            "hello",
            "/work",
            self.CAP_SECONDS,
            False,
        )
