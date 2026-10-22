from __future__ import annotations

from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.published_release import PublishedRelease
from slice_runner.domain.release_version import ReleaseVersion


class PublishedReleaseMother:
    @staticmethod
    def complete(version: str = "0.2.0", platform: BinaryPlatform = BinaryPlatform.MACOS_ARM64) -> PublishedRelease:
        return PublishedRelease(
            version=ReleaseVersion.of(version),
            assets=frozenset({f"slice_runner-{version}-py3-none-any.whl", f"slice-runner-tui-{platform}"}),
        )

    @staticmethod
    def without_the_binary_of(
        version: str = "0.2.0", platform: BinaryPlatform = BinaryPlatform.MACOS_ARM64
    ) -> PublishedRelease:
        other = next(candidate for candidate in BinaryPlatform if candidate is not platform)

        return PublishedRelease(
            version=ReleaseVersion.of(version),
            assets=frozenset({f"slice_runner-{version}-py3-none-any.whl", f"slice-runner-tui-{other}"}),
        )

    @staticmethod
    def without_the_wheel(
        version: str = "0.2.0", platform: BinaryPlatform = BinaryPlatform.MACOS_ARM64
    ) -> PublishedRelease:
        return PublishedRelease(version=ReleaseVersion.of(version), assets=frozenset({f"slice-runner-tui-{platform}"}))
