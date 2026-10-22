from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.read_newer_release import NewerRelease, ReadNewerRelease, ReadNewerReleaseParams
from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.exceptions import UnreadableReleaseError, UnsupportedPlatformError
from slice_runner.domain.host_platform import HostPlatform
from slice_runner.domain.program_installation import ProgramInstallation
from slice_runner.domain.program_releases import ProgramReleases
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.tests.mothers.published_release_mother import PublishedReleaseMother

INSTALLED = Path("/home/someone/.local/bin/slice-runner")
PARAMS = ReadNewerReleaseParams(running_program=INSTALLED)


class TestReadNewerRelease:
    @pytest.fixture
    def releases(self) -> Mock:
        releases: Mock = create_autospec(ProgramReleases, spec_set=True, instance=True)
        releases.latest.return_value = PublishedReleaseMother.complete("0.2.0")
        return releases

    @pytest.fixture
    def host(self) -> Mock:
        host: Mock = create_autospec(HostPlatform, spec_set=True, instance=True)
        host.binary_platform.return_value = BinaryPlatform.MACOS_ARM64
        return host

    @pytest.fixture
    def installation(self) -> Mock:
        installation: Mock = create_autospec(ProgramInstallation, spec_set=True, instance=True)
        installation.running_version.return_value = ReleaseVersion.of("0.1.0")
        installation.interface_version.return_value = ReleaseVersion.of("0.2.0")
        installation.installed_program.return_value = INSTALLED
        return installation

    @pytest.fixture
    def query(self, releases: Mock, installation: Mock, host: Mock) -> ReadNewerRelease:
        return ReadNewerRelease(releases=releases, installation=installation, host=host)

    def test_a_release_newer_than_the_running_version_is_reported_with_its_version(
        self, query: ReadNewerRelease
    ) -> None:
        assert query.execute(PARAMS) == NewerRelease.found(ReleaseVersion.of("0.2.0"))

    def test_the_running_version_being_the_latest_reports_none(
        self, query: ReadNewerRelease, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")

        assert query.execute(PARAMS) == NewerRelease.none()

    def test_a_release_that_cannot_be_read_reports_none_instead_of_failing(
        self, query: ReadNewerRelease, releases: Mock
    ) -> None:
        releases.latest.side_effect = UnreadableReleaseError("gh did not answer")

        assert query.execute(PARAMS) == NewerRelease.none()

    def test_versions_are_compared_by_number_and_not_by_text(
        self, query: ReadNewerRelease, releases: Mock, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.9.0")
        releases.latest.return_value = PublishedReleaseMother.complete("0.10.0")

        assert query.execute(PARAMS) == NewerRelease.found(ReleaseVersion.of("0.10.0"))

    def test_a_newer_release_without_the_binary_of_this_platform_reports_none(
        self, query: ReadNewerRelease, releases: Mock
    ) -> None:
        releases.latest.return_value = PublishedReleaseMother.without_the_binary_of("0.2.0", BinaryPlatform.MACOS_ARM64)

        assert query.execute(PARAMS) == NewerRelease.none()

    def test_a_machine_without_a_published_binary_reports_none_instead_of_failing(
        self, query: ReadNewerRelease, host: Mock
    ) -> None:
        host.binary_platform.side_effect = UnsupportedPlatformError("Windows AMD64 has no published binary")

        assert query.execute(PARAMS) == NewerRelease.none()

    @pytest.mark.parametrize("interface", ["0.1.0", None])
    def test_the_program_in_the_latest_version_with_an_older_or_unreadable_interface_reports_the_latest(
        self, query: ReadNewerRelease, installation: Mock, interface: str | None
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")
        installation.interface_version.return_value = None if interface is None else ReleaseVersion.of(interface)

        assert query.execute(PARAMS) == NewerRelease.found(ReleaseVersion.of("0.2.0"))

    @pytest.mark.parametrize("interface", ["0.2.0", "0.3.0"])
    def test_the_program_in_the_latest_version_with_the_latest_or_a_newer_interface_reports_none(
        self, query: ReadNewerRelease, installation: Mock, interface: str
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")
        installation.interface_version.return_value = ReleaseVersion.of(interface)

        assert query.execute(PARAMS) == NewerRelease.none()

    def test_an_older_interface_does_not_make_an_incomplete_latest_release_reportable(
        self, query: ReadNewerRelease, releases: Mock, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")
        installation.interface_version.return_value = ReleaseVersion.of("0.1.0")
        releases.latest.return_value = PublishedReleaseMother.without_the_binary_of("0.2.0", BinaryPlatform.MACOS_ARM64)

        assert query.execute(PARAMS) == NewerRelease.none()

    def test_a_program_that_is_not_the_installed_one_reports_none_even_with_a_newer_complete_release(
        self, query: ReadNewerRelease
    ) -> None:
        clone = ReadNewerReleaseParams(running_program=Path("/clone/.venv/bin/slice-runner"))

        assert query.execute(clone) == NewerRelease.none()

    def test_an_installation_that_cannot_be_read_reports_none_instead_of_failing(
        self, query: ReadNewerRelease, installation: Mock
    ) -> None:
        installation.installed_program.side_effect = UnreadableReleaseError("uv exited 2")

        assert query.execute(PARAMS) == NewerRelease.none()
