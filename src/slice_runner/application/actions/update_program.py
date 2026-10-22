from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import LiveRunsError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.host_platform import HostPlatform
    from slice_runner.domain.live_runs import LiveRuns
    from slice_runner.domain.program_installation import ProgramInstallation
    from slice_runner.domain.program_releases import ProgramReleases
    from slice_runner.domain.release_version import ReleaseVersion


@dataclass(frozen=True, kw_only=True, slots=True)
class WheelInstalled:
    program: Path


@dataclass(frozen=True, kw_only=True, slots=True)
class UpdateCompleted:
    pass


@dataclass(frozen=True, kw_only=True, slots=True)
class ReleaseIncomplete:
    version: ReleaseVersion


class UpdateProgram:
    def __init__(
        self,
        *,
        live_runs: LiveRuns,
        host: HostPlatform,
        releases: ProgramReleases,
        installation: ProgramInstallation,
    ) -> None:
        self._live_runs = live_runs
        self._host = host
        self._releases = releases
        self._installation = installation

    def execute(self) -> WheelInstalled | UpdateCompleted | ReleaseIncomplete:
        alive = self._live_runs.command_lines()
        if alive:
            raise LiveRunsError("live runs share the durable stores with the program:\n" + "\n".join(alive))

        platform = self._host.binary_platform()
        release = self._releases.latest()
        if not release.carries(platform):
            return ReleaseIncomplete(version=release.version)

        latest = release.version
        if latest.is_newer_than(self._installation.running_version()):
            return WheelInstalled(program=self._installation.install_wheel(self._releases.wheel(latest)))

        self._installation.install_binary(self._releases.binary(latest, platform))
        self._installation.install_skills()

        return UpdateCompleted()
