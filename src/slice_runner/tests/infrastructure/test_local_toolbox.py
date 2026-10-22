from __future__ import annotations

from unittest.mock import create_autospec

from slice_runner.infrastructure.local_toolbox import LocalToolbox
from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput
from slice_runner.tests.doubles import ScriptedProcess


class TestLocalToolbox:
    def test_it_asks_for_exactly_the_version_and_nothing_else(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="claude 2.1.4\n", stderr=""))

        LocalToolbox(process=process).version_of("claude")

        assert process.calls[0].argv == ["claude", "--version"]

    def test_the_version_printed_is_returned_stripped_of_its_trailing_newline(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="git version 2.51.0\n", stderr=""))

        assert LocalToolbox(process=process).version_of("git") == "git version 2.51.0"

    def test_an_executable_that_cannot_be_launched_reads_as_missing_instead_of_raising(self) -> None:
        process = create_autospec(Process, spec_set=True, instance=True)
        process.run.side_effect = ProcessNotRunnableError("nowhere: no such executable")

        assert LocalToolbox(process=process).version_of("nowhere") is None

    def test_a_nonzero_exit_reads_as_missing_too(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=127, stdout="", stderr="command not found"))

        assert LocalToolbox(process=process).version_of("nowhere") is None
