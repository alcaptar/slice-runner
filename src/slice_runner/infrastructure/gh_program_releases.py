from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadableReleaseError
from slice_runner.domain.program_releases import ProgramReleases
from slice_runner.domain.published_release import PublishedRelease
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError
from slice_runner.infrastructure.release_payload import ReleasePayload

if TYPE_CHECKING:
    from slice_runner.domain.binary_platform import BinaryPlatform
    from slice_runner.domain.release_version import ReleaseVersion
    from slice_runner.infrastructure.process import Process


class GhProgramReleases(ProgramReleases):
    def __init__(self, *, process: Process, repo: str) -> None:
        self._process = process
        self._repo = repo

    def latest(self) -> PublishedRelease:
        output = self._gh(["release", "view", "--repo", self._repo, "--json", "tagName,assets"])
        try:
            data = json.loads(output.stdout)
        except json.JSONDecodeError as error:
            raise UnreadableReleaseError(f"gh release view did not answer JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableReleaseError(f"gh release view has to answer an object, not {type(data).__name__}")

        return ReleasePayload.from_dict(data).to_domain()

    def wheel(self, version: ReleaseVersion) -> Path:
        return self._downloaded(version, PublishedRelease.wheel_name(version))

    def binary(self, version: ReleaseVersion, platform: BinaryPlatform) -> Path:
        return self._downloaded(version, PublishedRelease.binary_name(platform))

    def _downloaded(self, version: ReleaseVersion, asset: str) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="slice-runner-update-"))
        self._gh(
            ["release", "download", f"v{version}", "--repo", self._repo, "--pattern", asset, "--dir", str(directory)]
        )
        downloaded = directory / asset
        if not downloaded.is_file():
            raise UnreadableReleaseError(f"gh release download left no {asset} in v{version}")

        return downloaded

    def _gh(self, arguments: list[str]) -> ProcessOutput:
        try:
            output = self._process.run(["gh", *arguments], stdin="")
        except (ProcessTimedOutError, ProcessNotRunnableError) as error:
            raise UnreadableReleaseError(str(error)) from error
        if output.code != 0:
            raise UnreadableReleaseError(output.reason(tool="gh"))

        return output
