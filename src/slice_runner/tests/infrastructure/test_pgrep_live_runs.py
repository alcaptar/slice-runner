from __future__ import annotations

from slice_runner.infrastructure.pgrep_live_runs import PgrepLiveRuns
from slice_runner.tests.doubles import Answer, AnsweringByArgv


class TestTheRunsThatAreAlive:
    def test_each_process_whose_command_line_holds_the_run_subcommand_is_listed(self) -> None:
        process = AnsweringByArgv(
            Answer(to=("pgrep", "-fl"), stdout="4242 slice-runner run --repo a/b 12\n4343 slice-runner run 13\n")
        )

        lines = PgrepLiveRuns(process=process).command_lines()

        assert lines == ("4242 slice-runner run --repo a/b 12", "4343 slice-runner run 13")
        assert process.calls[0].argv == ["pgrep", "-fl", "slice-runner run "]

    def test_pgrep_finding_nothing_is_no_live_runs(self) -> None:
        process = AnsweringByArgv(Answer(to=("pgrep",), code=1))

        assert PgrepLiveRuns(process=process).command_lines() == ()
