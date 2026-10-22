from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.closure import Closure

if TYPE_CHECKING:
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class Transition:
    run: Run
    closure: Closure = field(default=Closure.open())
    wait_seconds: int = 0
