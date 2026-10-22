from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.infrastructure.stderr_turn_log import StderrTurnLog
from slice_runner.tests.mothers.turn_mother import TurnMother

if TYPE_CHECKING:
    import pytest


class TestStderrTurnLog:
    def test_the_turn_reaches_standard_error_as_the_contract_payload_and_never_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        StderrTurnLog().observe(TurnMother.first())

        output = capsys.readouterr()
        assert output.out == ""
        assert json.loads(output.err) == {
            "slice_id": "slice-05",
            "step": "implement",
            "number": 1,
            "tool": "Write",
            "target": "hello.py",
        }

    def test_two_consecutive_turns_land_on_two_separable_lines_and_never_on_a_single_run_together(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = StderrTurnLog()

        log.observe(TurnMother.first())
        log.observe(TurnMother.second())

        payloads = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
        assert [payload["number"] for payload in payloads] == [1, 2]
