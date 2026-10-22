from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.binary_platform import BinaryPlatform
    from slice_runner.domain.published_release import PublishedRelease
    from slice_runner.domain.release_version import ReleaseVersion


class ProgramReleases(ABC):
    @abstractmethod
    def latest(self) -> PublishedRelease: ...

    @abstractmethod
    def wheel(self, version: ReleaseVersion) -> Path: ...

    @abstractmethod
    def binary(self, version: ReleaseVersion, platform: BinaryPlatform) -> Path: ...
