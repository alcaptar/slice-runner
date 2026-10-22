from __future__ import annotations

from abc import ABC, abstractmethod


class PluginRegistry(ABC):
    @abstractmethod
    def enabled(self, name: str) -> bool: ...
