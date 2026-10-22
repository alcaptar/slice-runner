from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.prechecks import Prechecks, SourcesCheck

if TYPE_CHECKING:
    from slice_runner.domain.cited_source import CitedSource
    from slice_runner.domain.design import Design
    from slice_runner.domain.source import Source
    from slice_runner.domain.source_reader import SourceReader


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckSourcesParams:
    worktree: str
    sources: tuple[Source, ...]
    designs: tuple[Design, ...] = ()


class CheckSources:
    def __init__(self, *, sources: SourceReader) -> None:
        self._sources = sources

    def execute(self, params: CheckSourcesParams) -> PrecheckResult:
        check, reason = self._check(params)

        return PrecheckResult(outcome=Prechecks.of_the_sources(check), reason=reason)

    def _check(self, params: CheckSourcesParams) -> tuple[SourcesCheck, str | None]:
        try:
            self._read(params)
        except UnreadableSourceError as error:
            return SourcesCheck.UNREADABLE, str(error)
        except SourcesBudgetExceededError as error:
            return SourcesCheck.OVER_BUDGET, str(error)

        return SourcesCheck.READABLE, None

    def _read(self, params: CheckSourcesParams) -> tuple[CitedSource, ...]:
        if not params.designs:
            return self._sources.read_all(worktree=params.worktree, sources=params.sources)

        return self._sources.read_all(worktree=params.worktree, sources=params.sources, designs=params.designs)
