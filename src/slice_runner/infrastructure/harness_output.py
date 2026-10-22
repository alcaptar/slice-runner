from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar, Self

from pydantic import Field

from slice_runner.domain.exceptions import (
    InvalidHarnessOutputError,
    MeasuredCallError,
    MissingStructuredOutputError,
)
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.model_usage_payload import ModelUsageEntry
from slice_runner.infrastructure.open_vocabulary_model import OpenVocabularyModel
from slice_runner.infrastructure.permission_denial import PermissionDenial

if TYPE_CHECKING:
    from collections.abc import Iterator

    from slice_runner.infrastructure.process import ProcessOutput


class SessionEndCause:
    FIELDS: ClassVar[tuple[str, ...]] = ("subtype", "stop_reason", "terminal_reason")

    @classmethod
    def of_the_dict(cls, data: dict[str, object]) -> str:
        return cls._of_the_values({field: data.get(field) for field in cls.FIELDS})

    @classmethod
    def of_the_envelope(cls, envelope: HarnessOutput) -> str:
        return cls._of_the_values(
            {
                "subtype": envelope.subtype,
                "stop_reason": envelope.stop_reason,
                "terminal_reason": envelope.terminal_reason,
            }
        )

    @classmethod
    def _of_the_values(cls, values: dict[str, object]) -> str:
        present = [f"{field}={value!r}" for field, value in values.items() if value is not None]

        return cls._suffix(present)

    @staticmethod
    def _suffix(present: list[str]) -> str:
        if not present:
            return ""

        return f" (session ended with: {', '.join(present)})"


class HarnessOutput(OpenVocabularyModel):
    RESULT: ClassVar[str] = "result"

    is_error: bool = Field(strict=True)
    structured_output: dict[str, object] | None = None

    duration_api_ms: int | None = None
    duration_ms: int
    model_usage: dict[str, ModelUsageEntry] | None = Field(alias="modelUsage", default=None)
    num_turns: int
    permission_denials: tuple[PermissionDenial, ...] = ()
    session_id: str
    stop_reason: str | None = None
    subtype: str | None = None
    terminal_reason: str | None = None
    total_cost_usd: float
    ttft_ms: int | None = None

    def to_domain(self) -> HarnessSpend:
        return HarnessSpend(
            cost_usd=self.total_cost_usd,
            turns=self.num_turns,
            duration_ms=self.duration_ms,
            calls=1,
            models=tuple(sorted(self.model_usage)) if self.model_usage else (),
            input_tokens=sum(entry.input_tokens for entry in self.model_usage.values()) if self.model_usage else 0,
            output_tokens=sum(entry.output_tokens for entry in self.model_usage.values()) if self.model_usage else 0,
            cache_creation_tokens=sum(entry.cache_creation_input_tokens for entry in self.model_usage.values())
            if self.model_usage
            else 0,
            cache_read_tokens=sum(entry.cache_read_input_tokens for entry in self.model_usage.values())
            if self.model_usage
            else 0,
            ttft_ms=self.ttft_ms or 0,
            duration_api_ms=self.duration_api_ms or 0,
        )

    @contextmanager
    def measuring(self) -> Iterator[None]:
        try:
            yield
        except MeasuredCallError as error:
            error.spend = self.to_domain()
            raise

    def structured(self) -> dict[str, object]:
        if self.structured_output is None:
            raise MissingStructuredOutputError(
                f"the harness envelope has no `structured_output`{SessionEndCause.of_the_envelope(self)}"
            )

        return self.structured_output

    @classmethod
    def from_process(cls, output: ProcessOutput) -> Self:
        envelope = cls.from_dict(cls._decoded(output))
        with envelope.measuring():
            if envelope.is_error:
                raise InvalidHarnessOutputError("the harness marked the call as failed (`is_error`)")

        return envelope

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        try:
            return cls._validated(data, "the harness envelope is not the one we know", InvalidHarnessOutputError)
        except InvalidHarnessOutputError as error:
            cause = SessionEndCause.of_the_dict(data)
            if not cause:
                raise
            raise InvalidHarnessOutputError(f"{error}{cause}") from error

    @classmethod
    def _decoded(cls, output: ProcessOutput) -> dict[str, object]:
        lines = [line for line in output.stdout.splitlines() if line.strip()]
        if not lines:
            raise InvalidHarnessOutputError(
                f"the harness returned no JSON (code {output.code}): {cls._excerpt(output)}"
            )
        results = cls._results_streamed(lines)
        if results:
            return results[-1]

        return cls._only_object(lines[-1], output)

    @classmethod
    def _results_streamed(cls, lines: list[str]) -> list[dict[str, object]]:
        streamed = []
        for line in lines:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("type") == cls.RESULT:
                streamed.append(data)

        return streamed

    @classmethod
    def _only_object(cls, line: str, output: ProcessOutput) -> dict[str, object]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise InvalidHarnessOutputError(
                f"the harness returned no JSON (code {output.code}): {cls._excerpt(output)}"
            ) from error
        if not isinstance(data, dict):
            raise InvalidHarnessOutputError(f"the harness envelope has to be an object, not {type(data).__name__}")

        return data

    @staticmethod
    def _excerpt(output: ProcessOutput) -> str:
        return " ".join((output.stderr or output.stdout).split())[:200] or "(no output)"
