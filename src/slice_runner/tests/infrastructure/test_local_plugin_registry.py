from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadablePluginRegistryError
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_plugin_registry import LocalPluginRegistry

if TYPE_CHECKING:
    from pathlib import Path


class TestWhetherAPluginIsEnabled:
    @staticmethod
    def _write_settings(root: Path, enabled_plugins: dict[str, bool]) -> None:
        (root / "settings.json").write_text(json.dumps({"enabledPlugins": enabled_plugins}), encoding="utf-8")

    def test_a_plugin_enabled_under_any_marketplace_reads_as_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._write_settings(tmp_path, {"superpowers@claude-plugins-official": True})

        assert LocalPluginRegistry().enabled("superpowers")

    def test_a_plugin_disabled_reads_as_not_enabled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._write_settings(tmp_path, {"superpowers@claude-plugins-official": False})

        assert not LocalPluginRegistry().enabled("superpowers")

    def test_a_plugin_absent_from_the_map_reads_as_not_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._write_settings(tmp_path, {"python-practices@examples": True})

        assert not LocalPluginRegistry().enabled("superpowers")

    def test_a_machine_with_no_settings_file_at_all_reads_as_not_enabled_instead_of_failing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        assert not LocalPluginRegistry().enabled("superpowers")

    def test_settings_with_no_enabled_plugins_map_at_all_reads_as_not_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        (tmp_path / "settings.json").write_text(json.dumps({"model": "sonnet"}), encoding="utf-8")

        assert not LocalPluginRegistry().enabled("superpowers")

    def test_settings_that_are_not_valid_json_raise_instead_of_reading_as_not_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        (tmp_path / "settings.json").write_text("not json", encoding="utf-8")

        with pytest.raises(UnreadablePluginRegistryError):
            LocalPluginRegistry().enabled("superpowers")
