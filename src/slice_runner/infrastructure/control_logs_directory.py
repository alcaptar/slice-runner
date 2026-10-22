from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.durable_ledger import DurableLedger

if TYPE_CHECKING:
    from pathlib import Path


class ControlLogsDirectory:
    SEGMENT: ClassVar[str] = "controls"

    @classmethod
    def default(cls) -> Path:
        return DurableLedger.root() / cls.SEGMENT
