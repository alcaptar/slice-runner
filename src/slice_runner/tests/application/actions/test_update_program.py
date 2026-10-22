from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.update_program import (
    ReleaseIncomplete,
    UpdateCompleted,
    UpdateProgram,
    WheelInstalled,
)
from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.exceptions import LiveRunsError, UnsupportedPlatformError
from slice_runner.domain.host_platform import HostPlatform
from slice_runner.domain.live_runs import LiveRuns
from slice_runner.domain.program_installation import ProgramInstallation
from slice_runner.domain.program_releases import ProgramReleases
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.tests.mothers.published_release_mother import PublishedReleaseMother

_WHEEL = Path("/downloads/slice_runner-0.2.0-py3-none-any.whl")
_BINARY = Path("/downloads/slice-runner-tui-aarch64-apple-darwin")
_PROGRAM = Path("/uv/bin/slice-runner")


class TestUpdateProgram:
    @pytest.fixture
    def live_runs(self) -> Mock:
        live_runs: Mock = create_autospec(LiveRuns, spec_set=True, instance=True)
        live_runs.command_lines.return_value = ()
        return live_runs

    @pytest.fixture
    def host(self) -> Mock:
        host: Mock = create_autospec(HostPlatform, spec_set=True, instance=True)
        host.binary_platform.return_value = BinaryPlatform.MACOS_ARM64
        return host

    @pytest.fixture
    def releases(self) -> Mock:
        releases: Mock = create_autospec(ProgramReleases, spec_set=True, instance=True)
        releases.latest.return_value = PublishedReleaseMother.complete("0.2.0")
        releases.wheel.return_value = _WHEEL
        releases.binary.return_value = _BINARY
        return releases

    @pytest.fixture
    def installation(self) -> Mock:
        installation: Mock = create_autospec(ProgramInstallation, spec_set=True, instance=True)
        installation.running_version.return_value = ReleaseVersion.of("0.1.0")
        installation.interface_version.return_value = ReleaseVersion.of("0.2.0")
        installation.install_wheel.return_value = _PROGRAM
        return installation

    @pytest.fixture
    def action(self, live_runs: Mock, host: Mock, releases: Mock, installation: Mock) -> UpdateProgram:
        return UpdateProgram(live_runs=live_runs, host=host, releases=releases, installation=installation)

    def test_live_runs_stop_the_update_before_anything_is_fetched_or_installed(
        self, action: UpdateProgram, live_runs: Mock, releases: Mock, installation: Mock
    ) -> None:
        live_runs.command_lines.return_value = ("4242 slice-runner run --repo a/b 12",)

        with pytest.raises(LiveRunsError, match="slice-runner run --repo a/b 12"):
            action.execute()

        assert releases.mock_calls == []
        assert installation.install_wheel.mock_calls == []
        assert installation.install_binary.mock_calls == []
        assert installation.install_skills.mock_calls == []

    def test_a_platform_without_a_published_binary_stops_the_update_before_the_wheel_is_installed(
        self, action: UpdateProgram, host: Mock, releases: Mock, installation: Mock
    ) -> None:
        host.binary_platform.side_effect = UnsupportedPlatformError("Windows AMD64 has no published binary")

        with pytest.raises(UnsupportedPlatformError, match="Windows AMD64"):
            action.execute()

        assert releases.mock_calls == []
        assert installation.install_wheel.mock_calls == []

    def test_a_newer_release_installs_its_wheel_and_leaves_the_rest_to_the_program_it_just_installed(
        self, action: UpdateProgram, releases: Mock, installation: Mock
    ) -> None:
        outcome = action.execute()

        assert outcome == WheelInstalled(program=_PROGRAM)
        releases.wheel.assert_called_once_with(ReleaseVersion.of("0.2.0"))
        installation.install_wheel.assert_called_once_with(_WHEEL)
        assert installation.install_binary.mock_calls == []
        assert installation.install_skills.mock_calls == []

    def test_the_latest_release_downloads_the_binary_of_that_version_for_this_platform_and_copies_the_skills(
        self, action: UpdateProgram, releases: Mock, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")

        outcome = action.execute()

        assert outcome == UpdateCompleted()
        releases.binary.assert_called_once_with(ReleaseVersion.of("0.2.0"), BinaryPlatform.MACOS_ARM64)
        installation.install_binary.assert_called_once_with(_BINARY)
        installation.install_skills.assert_called_once_with()
        assert installation.install_wheel.mock_calls == []

    def test_an_older_interface_in_the_latest_program_installs_the_binary_and_the_skills_but_not_the_wheel(
        self, action: UpdateProgram, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")
        installation.interface_version.return_value = ReleaseVersion.of("0.1.0")

        outcome = action.execute()

        assert outcome == UpdateCompleted()
        assert len(installation.install_wheel.mock_calls) == 0
        assert len(installation.install_binary.mock_calls) == 1
        assert len(installation.install_skills.mock_calls) == 1

    def test_a_running_version_ahead_of_the_latest_release_is_not_downgraded(
        self, action: UpdateProgram, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.10.0")

        assert action.execute() == UpdateCompleted()
        assert installation.install_wheel.mock_calls == []

    @pytest.mark.parametrize("running", ["0.1.0", "0.2.0"])
    def test_an_incomplete_latest_release_installs_nothing_and_says_which_version_is_incomplete(
        self, action: UpdateProgram, releases: Mock, installation: Mock, running: str
    ) -> None:
        releases.latest.return_value = PublishedReleaseMother.without_the_binary_of("0.2.0", BinaryPlatform.MACOS_ARM64)
        installation.running_version.return_value = ReleaseVersion.of(running)

        outcome = action.execute()

        assert outcome == ReleaseIncomplete(version=ReleaseVersion.of("0.2.0"))
        assert installation.install_wheel.mock_calls == []
        assert installation.install_binary.mock_calls == []
        assert installation.install_skills.mock_calls == []
