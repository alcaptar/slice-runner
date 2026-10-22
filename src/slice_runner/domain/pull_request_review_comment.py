from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestReviewComment:
    body: str
    path: str
    line: int | None = None
