from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.infrastructure.gh_transient_failure import GhTransientFailure

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.gh_retry_policy import GhRetryPolicy
    from slice_runner.infrastructure.process import Process, ProcessOutput


@dataclass(frozen=True, kw_only=True, slots=True)
class GhCallOutcome:
    output: ProcessOutput
    retries: int

    @property
    def reason(self) -> str:
        stripped = self.output.stderr.strip()
        if self.retries:
            return f"{stripped} (retried {self.retries}x)"

        return stripped


class GhCall:
    def __init__(self, *, process: Process, policy: GhRetryPolicy, clock: Clock) -> None:
        self._process = process
        self._policy = policy
        self._clock = clock

    def run(self, argv: list[str], *, stdin: str = "", safe_to_repeat: bool) -> GhCallOutcome:
        output = self._process.run(argv, stdin=stdin)
        retries = 0
        while output.code != 0:
            decision = self._policy.after_a_failure(
                transient=GhTransientFailure.of(output.stderr),
                safe_to_repeat=safe_to_repeat,
                attempted=retries,
            )
            if not decision.retry:
                break

            self._clock.sleep(seconds=decision.wait_seconds)
            output = self._process.run(argv, stdin=stdin)
            retries += 1

        return GhCallOutcome(output=output, retries=retries)
