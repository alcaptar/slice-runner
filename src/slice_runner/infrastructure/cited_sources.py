from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.source import Source
    from slice_runner.domain.source_reader import SourceReader


class CitedSources:
    @staticmethod
    def of(heading: str, *, reader: SourceReader, worktree: str, sources: tuple[Source, ...]) -> list[str]:
        cited = reader.read_all(worktree=worktree, sources=sources)

        lines = [f"- {heading} ({len(cited)}):"]
        for one in cited:
            lines.append(f"  - {one.source.kind}: {one.source.path}")
            lines.extend(f"    {line}" for line in one.content.splitlines())

        return lines
