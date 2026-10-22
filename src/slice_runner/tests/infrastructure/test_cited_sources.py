from __future__ import annotations

from slice_runner.domain.source import Source, SourceKind
from slice_runner.infrastructure.cited_sources import CitedSources
from slice_runner.tests.doubles import RecordedSourceReader


class TestASourceIsCitedByItsPathNextToItsContent:
    def test_the_path_of_a_single_source_precedes_its_content_lines(self) -> None:
        reader = RecordedSourceReader(contents={"docs/a.md": "primera regla\nsegunda regla"})
        source = Source(kind=SourceKind.DOC, path="docs/a.md")

        lines = CitedSources.of("fuentes de convencion", reader=reader, worktree="/repo", sources=(source,))

        assert lines == [
            "- fuentes de convencion (1):",
            "  - doc: docs/a.md",
            "    primera regla",
            "    segunda regla",
        ]

    def test_each_of_several_sources_is_cited_right_before_its_own_content_and_not_mixed_with_another(self) -> None:
        reader = RecordedSourceReader(contents={"docs/a.md": "regla de a", "docs/b.md": "regla de b"})
        a, b = Source(kind=SourceKind.DOC, path="docs/a.md"), Source(kind=SourceKind.DOC, path="docs/b.md")

        lines = CitedSources.of("fuentes de convencion", reader=reader, worktree="/repo", sources=(a, b))

        assert lines == [
            "- fuentes de convencion (2):",
            "  - doc: docs/a.md",
            "    regla de a",
            "  - doc: docs/b.md",
            "    regla de b",
        ]

    def test_an_empty_declaration_carries_no_content_at_all(self) -> None:
        reader = RecordedSourceReader()

        lines = CitedSources.of("fuentes de convencion", reader=reader, worktree="/repo", sources=())

        assert lines == ["- fuentes de convencion (0):"]
