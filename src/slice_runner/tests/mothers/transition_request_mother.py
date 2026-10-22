from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.outcome import Outcome
    from slice_runner.domain.step import Step


class TransitionRequestMother:
    @staticmethod
    def asking(step: Step, outcome: Outcome, **spent: int) -> str:
        return json.dumps({"run": {"step": str(step), **spent}, "outcome": str(outcome)})

    @staticmethod
    def not_even_json() -> str:
        return "{'run': the shell ate the quotes"

    @staticmethod
    def with_a_step_nobody_declared() -> str:
        return json.dumps({"run": {"step": "deploy"}, "outcome": "done"})

    @staticmethod
    def with_a_counter_that_arrives_as_text() -> str:
        return json.dumps({"run": {"step": "run-controls", "control_retries": "1"}, "outcome": "failed"})
