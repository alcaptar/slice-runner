from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestTheConfiguredRoot:
    def test_it_honors_the_configuration_directory_variable_instead_of_a_fixed_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().root() == tmp_path

    def test_without_the_variable_it_falls_back_to_the_home_of_the_tool_and_expands_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ClaudeConfig.VARIABLE, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        assert LocalSkillLibrary().root() == tmp_path / ".claude"


class TestWhereTheYardstickLives:
    def test_both_trees_are_granted_because_the_two_skills_the_rubric_names_live_apart(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for tree in ("skills", "plugins"):
            (tmp_path / tree).mkdir()
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().directories() == (tmp_path / "skills", tmp_path / "plugins")

    def test_the_parent_is_granted_and_not_the_versioned_directory_of_a_plugin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        versioned = tmp_path / "plugins" / "cache" / "examples" / "python-practices" / "2.0.2"
        versioned.mkdir(parents=True)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        granted = LocalSkillLibrary().directories()

        assert granted == (tmp_path / "plugins",)
        assert all("2.0.2" not in str(directory) for directory in granted)

    def test_a_tree_that_is_not_there_is_not_granted_so_the_argv_cannot_name_a_missing_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "skills").mkdir()
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().directories() == (tmp_path / "skills",)

    def test_a_file_where_a_tree_should_be_is_not_granted_either(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "skills").write_text("not a directory", encoding="utf-8")
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().directories() == ()

    def test_a_machine_with_no_toolbox_at_all_grants_nothing_instead_of_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "nowhere"))

        assert LocalSkillLibrary().directories() == ()

    def test_without_the_variable_it_falls_back_to_the_home_of_the_tool_and_expands_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ClaudeConfig.VARIABLE, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".claude" / "skills").mkdir(parents=True)

        assert LocalSkillLibrary().directories() == (tmp_path / ".claude" / "skills",)

    def test_an_empty_variable_is_treated_as_absent_and_not_as_the_current_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, "")
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".claude" / "plugins").mkdir(parents=True)

        assert LocalSkillLibrary().directories() == (tmp_path / ".claude" / "plugins",)


class TestWhetherASkillIsInstalled:
    def test_a_skill_present_as_a_plain_directory_is_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skill = tmp_path / "skills" / "slice-spec"
        skill.mkdir(parents=True)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().installed("slice-spec") == skill

    def test_a_skill_installed_as_a_symlink_resolves_to_its_real_destination_not_the_link_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        checkout = tmp_path / "checkout" / "skills" / "slice-spec"
        checkout.mkdir(parents=True)
        (tmp_path / "skills").mkdir()
        symlink = tmp_path / "skills" / "slice-spec"
        symlink.symlink_to(checkout)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        installed = LocalSkillLibrary().installed("slice-spec")

        assert installed == checkout
        assert installed != symlink

    def test_a_skill_not_installed_reads_as_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "skills").mkdir()
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().installed("slice-spec") is None

    def test_a_file_in_place_of_the_skill_directory_is_not_installed_either(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "slice-spec").write_text("not a directory", encoding="utf-8")
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert LocalSkillLibrary().installed("slice-spec") is None
