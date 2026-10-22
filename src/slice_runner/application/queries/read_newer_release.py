from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from slice_runner.domain.exceptions import UnreadableReleaseError, UnsupportedPlatformError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.host_platform import HostPlatform
    from slice_runner.domain.program_installation import ProgramInstallation
    from slice_runner.domain.program_releases import ProgramReleases
    from slice_runner.domain.release_version import ReleaseVersion


@dataclass(frozen=True, kw_only=True, slots=True)
class NewerRelease:
    versions: tuple[ReleaseVersion, ...]

    @classmethod
    def found(cls, version: ReleaseVersion) -> Self:
        return cls(versions=(version,))

    @classmethod
    def none(cls) -> Self:
        return cls(versions=())


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadNewerReleaseParams:
    running_program: Path


class ReadNewerRelease:
    def __init__(self, *, releases: ProgramReleases, installation: ProgramInstallation, host: HostPlatform) -> None:
        self._releases = releases
        self._installation = installation
        self._host = host

    def execute(self, params: ReadNewerReleaseParams) -> NewerRelease:
        try:
            if params.running_program != self._installation.installed_program():
                return NewerRelease.none()

            platform = self._host.binary_platform()
            latest = self._releases.latest()
            if not latest.carries(platform):
                return NewerRelease.none()

            if self._is_behind(latest.version):
                return NewerRelease.found(latest.version)
        except (UnreadableReleaseError, UnsupportedPlatformError):
            return NewerRelease.none()

        return NewerRelease.none()

    def _is_behind(self, latest: ReleaseVersion) -> bool:
        if latest.is_newer_than(self._installation.running_version()):
            return True
        interface = self._installation.interface_version()

        return interface is None or latest.is_newer_than(interface)
