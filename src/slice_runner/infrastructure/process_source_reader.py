from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.cited_source import CitedSource
from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError
from slice_runner.domain.source_reader import SourceReader

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.design import Design
    from slice_runner.domain.source import Source
    from slice_runner.infrastructure.process import Process


class ProcessSourceReader(SourceReader):
    def __init__(self, *, process: Process, budgets: Budgets) -> None:
        self._process = process
        self._budgets = budgets

    def read_all(
        self, *, worktree: str, sources: tuple[Source, ...], designs: tuple[Design, ...] = ()
    ) -> tuple[CitedSource, ...]:
        cited = tuple(
            CitedSource(source=source, content=self._read(worktree=worktree, source=source)) for source in sources
        )
        weighed = [(one.source.path, len(one.content)) for one in cited]
        weighed.extend((design.name, len(design.html)) for design in designs)
        total_chars = sum(chars for _, chars in weighed)
        if self._budgets.sources_exceed(total_chars):
            weights = ", ".join(f"{name}: {chars} characters" for name, chars in weighed)
            raise SourcesBudgetExceededError(
                f"the {len(weighed)} declared source(s) and design(s) add up to {total_chars} characters, over the "
                f"{self._budgets.sources_max_chars} the budget allows: {weights}"
            )

        return cited

    def _read(self, *, worktree: str, source: Source) -> str:
        argv = ["cat", source.path]
        output = self._process.run(argv, stdin="", cwd=worktree)
        if output.code != 0:
            raise UnreadableSourceError(
                f"{source.path} could not be read under {worktree}: {output.reason(tool=argv[0])}"
            )

        return output.stdout
