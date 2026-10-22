from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class EventCursor:
    offset: int

    @classmethod
    def start(cls) -> EventCursor:
        return cls(offset=0)
