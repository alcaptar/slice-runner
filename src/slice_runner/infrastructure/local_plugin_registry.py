from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadablePluginRegistryError
from slice_runner.domain.plugin_registry import PluginRegistry
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.enabled_plugins_payload import EnabledPluginsPayload

if TYPE_CHECKING:
    from pathlib import Path


class LocalPluginRegistry(PluginRegistry):
    def enabled(self, name: str) -> bool:
        settings = ClaudeConfig.root() / "settings.json"
        if not settings.is_file():
            return False

        payload = EnabledPluginsPayload.from_dict(self._decoded(settings))
        prefix = f"{name}@"

        return any(value for key, value in payload.enabled_plugins.items() if key.startswith(prefix))

    @staticmethod
    def _decoded(settings: Path) -> dict[str, object]:
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise UnreadablePluginRegistryError(f"{settings} is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadablePluginRegistryError(f"{settings} has to be an object, not {type(data).__name__}")

        return data
