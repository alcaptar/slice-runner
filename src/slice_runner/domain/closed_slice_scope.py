from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSliceScope:
    repo: str | None
    issues: tuple[int, ...]
    since: datetime
    until: datetime

    @classmethod
    def of_a_repo_between(cls, *, repo: str | None, since: datetime, until: datetime) -> Self:
        return cls(repo=repo, issues=(), since=since, until=until)

    @classmethod
    def of_these_issues(cls, *, repo: str, issues: tuple[int, ...]) -> Self:
        return cls(
            repo=repo, issues=issues, since=datetime.min.replace(tzinfo=UTC), until=datetime.max.replace(tzinfo=UTC)
        )

    def contains(self, ts: datetime) -> bool:
        return self.since <= ts <= self.until
