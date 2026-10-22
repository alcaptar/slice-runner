from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode

if TYPE_CHECKING:
    import pytest


class TestTheCommandThatDiscoversTheControls:
    @staticmethod
    def _write(root: Path, relative_path: str, content: str) -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _lines_printed_for(repo: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
        code = Cli.main(["discover-controls", str(repo)])

        assert code == ExitCode.OK
        return capsys.readouterr().out.splitlines()

    def test_a_repo_with_a_makefile_and_a_pyproject_prints_the_literal_candidates(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(
            tmp_path,
            "Makefile",
            ".PHONY: check test\n\n# runs the linter, the types and the tests\n"
            "check:\n\truff check .\n\ntest:\n\tpytest\n",
        )
        self._write(tmp_path, "pyproject.toml", "[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n")

        assert self._lines_printed_for(tmp_path, capsys) == [
            "check: make check  # runs the linter, the types and the tests (makefile)",
            "test: make test  # (makefile)",
            "ruff: ruff check .  # configured in [tool.ruff] (pyproject)",
            "mypy: mypy .  # configured in [tool.mypy] (pyproject)",
        ]

    def test_an_empty_repo_prints_nothing_because_an_empty_list_means_ask_and_not_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert self._lines_printed_for(tmp_path, capsys) == []

    def test_a_blank_line_cuts_the_hint_of_the_comment_above(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "Makefile", "# header of the file\n\ntest:\n\tpytest\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["test: make test  # (makefile)"]

    def test_hidden_targets_variables_and_pattern_rules_are_not_invocable_as_controls(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "Makefile", ".PHONY: test\nSHELL := /bin/bash\n%.o: %.c\n\tcc $<\ntest:\n\tpytest\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["test: make test  # (makefile)"]

    def test_a_target_declared_twice_is_listed_once(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self._write(tmp_path, "Makefile", "test:\n\tpytest\ntest: extra\n\techo x\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["test: make test  # (makefile)"]

    def test_a_recipe_line_with_a_colon_does_not_declare_a_target(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "Makefile", "test:\n\techo something: with two colons\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["test: make test  # (makefile)"]

    def test_the_tools_configured_in_the_pyproject_are_listed_with_their_signal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(
            tmp_path,
            "pyproject.toml",
            "[tool.ruff.format]\nquote-style = 'double'\n\n[tool.pytest.ini_options]\ntestpaths = []\n",
        )

        assert self._lines_printed_for(tmp_path, capsys) == [
            "ruff: ruff check .  # configured in [tool.ruff] (pyproject)",
            "format: ruff format --check .  # configured in [tool.ruff.format] (pyproject)",
            "pytest: pytest  # configured in [tool.pytest.ini_options] (pyproject)",
        ]

    def test_a_pyproject_without_tools_contributes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')

        assert self._lines_printed_for(tmp_path, capsys) == []

    def test_an_unreadable_pyproject_does_not_hide_the_candidates_of_the_makefile(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "Makefile", "test:\n\tpytest\n")
        self._write(tmp_path, "pyproject.toml", "this is not toml [[[\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["test: make test  # (makefile)"]

    def test_the_makefile_comes_before_the_pyproject_because_everything_may_run_in_a_container_through_make(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._write(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = []\n")
        self._write(tmp_path, "Makefile", "test:\n\tdocker compose run pytest\n")

        assert self._lines_printed_for(tmp_path, capsys) == [
            "test: make test  # (makefile)",
            "pytest: pytest  # configured in [tool.pytest.ini_options] (pyproject)",
        ]

    def test_a_tox_ini_is_a_signal(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self._write(tmp_path, "tox.ini", "[tox]\nenvlist = py311\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["tox: tox  # there is a tox.ini (tox)"]

    def test_a_makefile_named_in_lowercase_is_found(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self._write(tmp_path, "GNUmakefile", "lint:\n\truff check .\n")

        assert self._lines_printed_for(tmp_path, capsys) == ["lint: make lint  # (makefile)"]

    def test_this_repo_lists_check_among_its_candidates(self, capsys: pytest.CaptureFixture[str]) -> None:
        repo = Path(__file__).resolve().parents[4]

        assert "check: make check" in "\n".join(self._lines_printed_for(repo, capsys))
