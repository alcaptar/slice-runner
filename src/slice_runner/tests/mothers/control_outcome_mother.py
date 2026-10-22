from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from slice_runner.domain.control_outcome import ControlOutcome
from slice_runner.domain.control_status import ControlStatus


class ControlOutcomeMother:
    LOG: ClassVar[Path] = Path("/tmp/slice-runner/logs/lint.log")

    @classmethod
    def green(cls) -> ControlOutcome:
        return ControlOutcome(status=ControlStatus.GREEN, log=cls.LOG)

    @classmethod
    def red(cls) -> ControlOutcome:
        return ControlOutcome(status=ControlStatus.RED, log=cls.LOG)

    @classmethod
    def unknown(cls) -> ControlOutcome:
        return ControlOutcome(status=ControlStatus.UNKNOWN)
