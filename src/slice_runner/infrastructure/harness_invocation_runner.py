from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.activity_actor import ActivityActor
from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.harness_turn_watch import HarnessTurnWatch

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
    from slice_runner.infrastructure.process import Process


class HarnessInvocation(ABC):
    @property
    @abstractmethod
    def argv(self) -> list[str]: ...

    @property
    @abstractmethod
    def text(self) -> str: ...

    @property
    @abstractmethod
    def cwd(self) -> str: ...


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessCallSubject:
    coordinates: SliceCoordinates
    worktree: str


class HarnessInvocationRunner:
    def __init__(self, *, process: Process, telemetry: HarnessTelemetry) -> None:
        self._process = process
        self._telemetry = telemetry

    def call(self, invocation: HarnessInvocation, *, step: Step, subject: HarnessCallSubject) -> HarnessOutput:
        self._telemetry.activity.restart(subject.coordinates)
        watch = HarnessTurnWatch(
            turns=self._telemetry.turns,
            activity=self._telemetry.activity,
            coordinates=subject.coordinates,
            actor=ActivityActor.of_the_harness_call_at(step),
            step=step,
        )
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._telemetry.trace.record(
            HarnessCall(coordinates=subject.coordinates, step=step, session=envelope.session_id)
        )
        self._telemetry.spend_log.record(
            HarnessCallSpend(coordinates=subject.coordinates, session=envelope.session_id, spend=envelope.to_domain())
        )
        self._telemetry.tool_uses.record_after(subject, step=step, session=envelope.session_id)

        return envelope
