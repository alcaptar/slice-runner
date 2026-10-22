from __future__ import annotations

import json
from typing import Self

from slice_runner.domain.exceptions import UnreadableRunError
from slice_runner.domain.outcome import Outcome
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.run_payload import RunPayload


class TransitionRequestPayload(ContractModel):
    run: RunPayload
    outcome: Outcome

    @classmethod
    def read(cls, text: str) -> Self:
        return cls._validated(
            cls._decoded(text), "the run to advance is not the one this program knows", UnreadableRunError
        )

    @staticmethod
    def _decoded(text: str) -> dict[str, object]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise UnreadableRunError(f"the run has to arrive as JSON on standard input: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableRunError(f"the run has to be an object, not {type(data).__name__}")

        return data
