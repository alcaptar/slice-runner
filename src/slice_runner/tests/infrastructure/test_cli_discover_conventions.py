from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.convention_source_discovery import ConventionSourceDiscovery
from slice_runner.infrastructure.exit_code import ExitCode

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestTheCommandThatDiscoversTheConventionSources:
    @staticmethod
    def _write(root: Path, *relative_paths: str) -> None:
        for relative_path in relative_paths:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")

    @classmethod
    def _write_a_repo_with_conventions(cls, root: Path) -> None:
        cls._write(
            root,
            ".claude/CLAUDE.md",
            ".claude/rules/conventions/testing.md",
            ".claude/rules/conventions/delivery.md",
            ".claude/skills/nuevo-caso-de-uso/SKILL.md",
            ".claude/skills/deprecar-endpoint/SKILL.md",
            "CONTRIBUTING.md",
            "src/app/CLAUDE.md",
            ".git/config",
            "__pycache__/x.pyc",
            "node_modules/dep/CLAUDE.md",
            "src/app/service.py",
        )

    @staticmethod
    def _lines_printed_for(repo: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
        code = Cli.main(["discover-conventions", str(repo)])

        assert code == ExitCode.OK
        return capsys.readouterr().out.splitlines()

    def test_it_prints_the_documents_and_then_the_skills_of_a_repo_as_literal_lines(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write_a_repo_with_conventions(tmp_path)

        assert self._lines_printed_for(tmp_path, capsys) == [
            "doc: .claude/CLAUDE.md",
            "doc: .claude/rules/",
            "doc: CONTRIBUTING.md",
            "doc: src/app/CLAUDE.md",
            "skill: .claude/skills/deprecar-endpoint/",
            "skill: .claude/skills/nuevo-caso-de-uso/",
        ]

    def test_a_convention_directory_is_listed_once_at_its_outermost_level(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write_a_repo_with_conventions(tmp_path)

        lines = self._lines_printed_for(tmp_path, capsys)

        assert "doc: .claude/rules/" in lines
        assert "doc: .claude/rules/conventions/" not in lines
        assert "doc: .claude/rules/conventions/testing.md" not in lines

    def test_it_does_not_descend_into_the_directories_that_are_noise(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        noisy = (f"{noise}/CLAUDE.md" for noise in sorted(ConventionSourceDiscovery.NOISE_DIRECTORIES))
        self._write(tmp_path, "CLAUDE.md", *noisy)

        assert self._lines_printed_for(tmp_path, capsys) == ["doc: CLAUDE.md"]

    def test_the_documents_come_sorted_before_the_skills_which_come_sorted_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write_a_repo_with_conventions(tmp_path)

        lines = self._lines_printed_for(tmp_path, capsys)

        documents = [line for line in lines if line.startswith("doc: ")]
        skills = [line for line in lines if line.startswith("skill: ")]
        assert lines == documents + skills
        assert documents == sorted(documents)
        assert skills == sorted(skills)

    def test_a_hidden_directory_inside_the_skills_is_tool_state_and_not_a_skill(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, ".claude/skills/nuevo-caso-de-uso/SKILL.md", ".claude/skills/.tool-state/config.json")

        assert self._lines_printed_for(tmp_path, capsys) == ["skill: .claude/skills/nuevo-caso-de-uso/"]

    def test_a_repo_without_candidates_prints_nothing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self._write(tmp_path, "src/main.py")

        assert self._lines_printed_for(tmp_path, capsys) == []

    def test_a_repo_with_a_single_document_prints_a_single_doc_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "CLAUDE.md")

        assert self._lines_printed_for(tmp_path, capsys) == ["doc: CLAUDE.md"]
