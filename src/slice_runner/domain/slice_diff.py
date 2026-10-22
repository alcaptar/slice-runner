from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff_stats import DiffStats


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceDiff:
    text: str
    files: tuple[str, ...]
    stats: DiffStats

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def repeats(self, fingerprint: str | None) -> bool:
        return fingerprint is not None and fingerprint == self.fingerprint
