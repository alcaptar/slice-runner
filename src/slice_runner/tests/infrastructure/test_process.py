from __future__ import annotations

from slice_runner.infrastructure.process import ProcessOutput


class TestProcessOutputReason:
    def test_stderr_wins_when_it_carries_something(self) -> None:
        output = ProcessOutput(code=1, stdout="something on stdout", stderr="the real reason")

        assert output.reason(tool="git") == "the real reason"

    def test_stdout_is_used_when_stderr_is_empty(self) -> None:
        output = ProcessOutput(code=1, stdout="the reason lives here", stderr="")

        assert output.reason(tool="git") == "the reason lives here"

    def test_neither_stream_falls_back_to_the_tool_and_the_exit_code(self) -> None:
        output = ProcessOutput(code=7, stdout="", stderr="")

        assert output.reason(tool="git") == "git exited 7"
