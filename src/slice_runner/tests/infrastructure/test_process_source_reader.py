from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.cited_source import CitedSource
from slice_runner.domain.design import Design
from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError
from slice_runner.domain.source import Source, SourceKind
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.tests.doubles import Answer, AnsweringByArgv

if TYPE_CHECKING:
    from collections.abc import Callable

    from slice_runner.infrastructure.process import ProcessOutput

_WORKTREE = "/worktree"


class _AnsweringByArgvRememberingTheDirectory(AnsweringByArgv):
    def __init__(self, *answers: Answer) -> None:
        super().__init__(*answers)
        self.directories: list[str | None] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.directories.append(cwd)

        return super().run(argv, stdin=stdin, cwd=cwd, on_line=on_line)


class _Reading:
    @staticmethod
    def _reader(*answers: Answer, budgets: Budgets | None = None) -> ProcessSourceReader:
        return ProcessSourceReader(process=AnsweringByArgv(*answers), budgets=budgets or Budgets())

    @staticmethod
    def _doc(path: str) -> Source:
        return Source(kind=SourceKind.DOC, path=path)


class TestReadingADeclaredSource(_Reading):
    def test_the_content_of_an_existing_file_is_returned_cited_by_its_source(self) -> None:
        reader = self._reader(Answer.to_exactly("cat", "doc.md", stdout="la regla es esta"))
        source = self._doc("doc.md")

        cited = reader.read_all(worktree=_WORKTREE, sources=(source,))

        assert cited == (CitedSource(source=source, content="la regla es esta"),)

    def test_several_declared_sources_are_all_read_and_cited_in_order(self) -> None:
        reader = self._reader(
            Answer.to_exactly("cat", "a.md", stdout="contenido de a"),
            Answer.to_exactly("cat", "b.md", stdout="contenido de b"),
        )
        a, b = self._doc("a.md"), self._doc("b.md")

        cited = reader.read_all(worktree=_WORKTREE, sources=(a, b))

        assert cited == (
            CitedSource(source=a, content="contenido de a"),
            CitedSource(source=b, content="contenido de b"),
        )

    def test_every_declared_source_is_read_from_inside_the_worktree_of_the_slice(self) -> None:
        process = _AnsweringByArgvRememberingTheDirectory(
            Answer.to_exactly("cat", "a.md", stdout="a"), Answer.to_exactly("cat", "b.md", stdout="b")
        )
        reader = ProcessSourceReader(process=process, budgets=Budgets())

        reader.read_all(worktree=_WORKTREE, sources=(self._doc("a.md"), self._doc("b.md")))

        assert process.directories == [_WORKTREE, _WORKTREE]

    def test_a_declared_source_that_does_not_exist_is_unreadable_before_any_prompt_is_built(self) -> None:
        reader = self._reader(
            Answer.to_exactly("cat", "missing.md", code=1, stderr="cat: missing.md: No such file or directory")
        )

        with pytest.raises(UnreadableSourceError, match=r"missing\.md"):
            reader.read_all(worktree=_WORKTREE, sources=(self._doc("missing.md"),))

    def test_the_reason_the_tool_gave_travels_in_the_message_of_an_unreadable_source(self) -> None:
        reader = self._reader(Answer.to_exactly("cat", "doc.md", code=1, stderr="cat: doc.md: Permission denied"))

        with pytest.raises(UnreadableSourceError, match="Permission denied"):
            reader.read_all(worktree=_WORKTREE, sources=(self._doc("doc.md"),))


class TestTheSizeCapOnDeclaredSources(_Reading):
    def test_content_exactly_at_the_cap_is_returned_without_raising(self) -> None:
        reader = self._reader(
            Answer.to_exactly("cat", "doc.md", stdout="a" * 10), budgets=Budgets(sources_max_chars=10)
        )

        cited = reader.read_all(worktree=_WORKTREE, sources=(self._doc("doc.md"),))

        assert cited[0].content == "a" * 10

    def test_content_one_character_over_the_cap_stops_the_run_instead_of_sending_a_prompt(self) -> None:
        reader = self._reader(
            Answer.to_exactly("cat", "doc.md", stdout="a" * 11), budgets=Budgets(sources_max_chars=10)
        )

        with pytest.raises(SourcesBudgetExceededError):
            reader.read_all(worktree=_WORKTREE, sources=(self._doc("doc.md"),))

    def test_the_message_names_every_source_and_how_much_it_weighs_against_the_cap(self) -> None:
        reader = self._reader(
            Answer.to_exactly("cat", "a.md", stdout="a" * 7),
            Answer.to_exactly("cat", "b.md", stdout="b" * 4),
            budgets=Budgets(sources_max_chars=10),
        )

        with pytest.raises(SourcesBudgetExceededError, match=r"a\.md: 7 characters.*b\.md: 4 characters"):
            reader.read_all(worktree=_WORKTREE, sources=(self._doc("a.md"), self._doc("b.md")))


class TestTheSizeCapCountsTheDesignsAlongsideTheSources(_Reading):
    def test_a_design_that_pushes_the_sum_one_character_over_the_cap_stops_the_run(self) -> None:
        reader = self._reader(Answer.to_exactly("cat", "doc.md", stdout="a" * 6), budgets=Budgets(sources_max_chars=10))

        with pytest.raises(SourcesBudgetExceededError, match=r"tablero: 5 characters"):
            reader.read_all(
                worktree=_WORKTREE, sources=(self._doc("doc.md"),), designs=(Design(name="tablero", html="h" * 5),)
            )

    def test_a_design_that_leaves_the_sum_exactly_at_the_cap_is_returned_without_raising(self) -> None:
        reader = self._reader(Answer.to_exactly("cat", "doc.md", stdout="a" * 6), budgets=Budgets(sources_max_chars=10))
        source = self._doc("doc.md")

        cited = reader.read_all(worktree=_WORKTREE, sources=(source,), designs=(Design(name="tablero", html="h" * 4),))

        assert cited == (CitedSource(source=source, content="a" * 6),)
