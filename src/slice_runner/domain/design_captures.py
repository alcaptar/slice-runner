from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.design_capture import DesignCapture


@dataclass(frozen=True, kw_only=True, slots=True)
class DesignCaptures:
    captures: tuple[DesignCapture, ...]
