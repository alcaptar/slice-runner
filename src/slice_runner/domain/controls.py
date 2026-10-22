from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.control_command import ControlCommand


@dataclass(frozen=True, kw_only=True, slots=True)
class Controls:
    commands: tuple[ControlCommand, ...]
    exemption_reason: str | None

    @property
    def declared(self) -> bool:
        return bool(self.commands) or self.exemption_reason is not None
