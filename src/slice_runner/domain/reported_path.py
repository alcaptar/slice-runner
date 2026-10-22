from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.path_kind import PathKind


@dataclass(frozen=True, kw_only=True, slots=True)
class ReportedPath:
    path: str
    kind: PathKind
