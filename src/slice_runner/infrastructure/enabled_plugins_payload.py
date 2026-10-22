from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadablePluginRegistryError
from slice_runner.infrastructure.contract_model import ContractModel


class EnabledPluginsPayload(ContractModel):
    enabled_plugins: dict[str, bool] = Field(alias="enabledPlugins", default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(enabledPlugins=data.get("enabledPlugins")),
            "Claude Code's settings do not carry a readable enabledPlugins map",
            UnreadablePluginRegistryError,
        )
