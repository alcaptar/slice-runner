from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.binary_platform import BinaryPlatform
    from slice_runner.domain.release_version import ReleaseVersion


@dataclass(frozen=True, kw_only=True, slots=True)
class PublishedRelease:
    version: ReleaseVersion
    assets: frozenset[str]

    def carries(self, platform: BinaryPlatform) -> bool:
        return {self.wheel_name(self.version), self.binary_name(platform)} <= self.assets

    @staticmethod
    def wheel_name(version: ReleaseVersion) -> str:
        return f"slice_runner-{version}-py3-none-any.whl"

    @staticmethod
    def binary_name(platform: BinaryPlatform) -> str:
        return f"slice-runner-tui-{platform}"
