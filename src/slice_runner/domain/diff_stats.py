from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class DiffStats:
    files_changed: int
    lines_added: int
    lines_deleted: int
