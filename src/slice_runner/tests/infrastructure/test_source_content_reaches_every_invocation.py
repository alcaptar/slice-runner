from __future__ import annotations

from dataclasses import replace

from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.process_source_reader import ProcessSourceReader
from slice_runner.tests.doubles import Answer, AnsweringByArgv, RecordedSourceReader
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

_LITERAL_LINE_OF_CLAUDE_MD = "# slice-runner — instrucciones del repo"


class TestEachInvocationCarriesTheLiteralContentOfItsDeclaredSource:
    @staticmethod
    def _reader_of_a_claude_md_with_the_literal_line() -> ProcessSourceReader:
        process = AnsweringByArgv(Answer.to_exactly("cat", "CLAUDE.md", stdout=f"{_LITERAL_LINE_OF_CLAUDE_MD}\nreglas"))

        return ProcessSourceReader(process=process, budgets=Budgets())

    def test_the_implementer_carries_a_literal_line_of_the_declared_source(self) -> None:
        reader = self._reader_of_a_claude_md_with_the_literal_line()

        text = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=reader).text

        assert _LITERAL_LINE_OF_CLAUDE_MD in text

    def test_the_judge_carries_a_literal_line_of_the_declared_source(self) -> None:
        reader = self._reader_of_a_claude_md_with_the_literal_line()

        text = JudgeInvocation(
            judge=JudgeMother.adversarial(), review=SliceUnderReviewMother.of_the_slice(), reader=reader
        ).text

        assert _LITERAL_LINE_OF_CLAUDE_MD in text


class TestTheTwoInvocationsAgreeOnTheSameSourcesTextForTheSameSources:
    @staticmethod
    def _fuentes_section(text: str) -> str:
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("- fuentes de convencion"))
        end = start + 1
        while end < len(lines) and lines[end].startswith(" "):
            end += 1

        return "\n".join(lines[start:end])

    def test_the_fuentes_section_is_character_for_character_identical_across_the_two(self) -> None:
        reader = RecordedSourceReader(contents={"CLAUDE.md": "linea unica de la convencion"})

        implementer_text = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=reader).text
        judge_text = JudgeInvocation(
            judge=JudgeMother.adversarial(), review=SliceUnderReviewMother.of_the_slice(), reader=reader
        ).text

        sections = {self._fuentes_section(implementer_text), self._fuentes_section(judge_text)}
        assert len(sections) == 1


class TestTheTwoInvocationsAgreeOnTheSameWorkingDirectory:
    def test_the_two_invocations_agree_that_the_cwd_is_the_worktree_and_not_the_repo_slug(self) -> None:
        worktree = AssignmentMother.WORKTREE
        reader = RecordedSourceReader()

        implementer = ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=reader)
        judge = JudgeInvocation(
            judge=JudgeMother.adversarial(),
            review=replace(SliceUnderReviewMother.of_the_slice(), worktree=worktree),
            reader=reader,
        )

        assert implementer.cwd == judge.cwd == worktree
