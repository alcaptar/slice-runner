from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.update_program import UpdateProgram
from slice_runner.application.queries.read_newer_release import ReadNewerRelease
from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.exceptions import UnreadableReleaseError, UnsupportedPlatformError
from slice_runner.domain.host_platform import HostPlatform
from slice_runner.domain.live_runs import LiveRuns
from slice_runner.domain.program_installation import ProgramInstallation
from slice_runner.domain.program_releases import ProgramReleases
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.tests.doubles import (
    MissingExecutableReplacement,
    RecordedReplacement,
    ReplacementRequestedError,
)
from slice_runner.tests.mothers.published_release_mother import PublishedReleaseMother

INSTALLED = Path("/home/someone/.local/bin/slice-runner")


class UpdatePorts:
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
        releases.wheel.return_value = Path("/downloads/slice_runner-0.2.0-py3-none-any.whl")
        releases.binary.return_value = Path("/downloads/slice-runner-tui-aarch64-apple-darwin")
        return releases

    @pytest.fixture
    def installation(self) -> Mock:
        installation: Mock = create_autospec(ProgramInstallation, spec_set=True, instance=True)
        installation.running_version.return_value = ReleaseVersion.of("0.1.0")
        installation.interface_version.return_value = ReleaseVersion.of("0.2.0")
        installation.installed_program.return_value = INSTALLED
        installation.install_wheel.return_value = Path("/home/someone/.local/bin/slice-runner")
        return installation

    @pytest.fixture
    def action(self, live_runs: Mock, host: Mock, releases: Mock, installation: Mock) -> UpdateProgram:
        return UpdateProgram(live_runs=live_runs, host=host, releases=releases, installation=installation)

    @pytest.fixture
    def query(self, releases: Mock, installation: Mock, host: Mock) -> ReadNewerRelease:
        return ReadNewerRelease(releases=releases, installation=installation, host=host)


class TestTheUpdateThatTheProgramRefuses(UpdatePorts):
    def test_live_runs_exit_with_their_own_code_and_name_each_run_on_stderr(
        self, action: UpdateProgram, live_runs: Mock, installation: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        live_runs.command_lines.return_value = ("4242 slice-runner run --repo a/b 12", "4343 slice-runner run 13")

        code = Cli.update(action=action, replacement=RecordedReplacement())

        captured = capsys.readouterr()
        assert code == ExitCode.LIVE_RUNS
        assert "4242 slice-runner run --repo a/b 12" in captured.err
        assert "4343 slice-runner run 13" in captured.err
        assert captured.out == ""
        assert installation.install_wheel.mock_calls == []

    def test_a_platform_without_a_binary_exits_with_its_own_code_and_names_the_platform(
        self, action: UpdateProgram, host: Mock, installation: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        host.binary_platform.side_effect = UnsupportedPlatformError("Windows AMD64 has no published binary")

        code = Cli.update(action=action, replacement=RecordedReplacement())

        assert code == ExitCode.UNSUPPORTED_PLATFORM
        assert "Windows AMD64" in capsys.readouterr().err
        assert installation.install_wheel.mock_calls == []

    def test_an_incomplete_release_exits_with_its_own_code_and_names_the_version_on_stderr(
        self, action: UpdateProgram, releases: Mock, installation: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        releases.latest.return_value = PublishedReleaseMother.without_the_wheel("0.2.0", BinaryPlatform.MACOS_ARM64)

        code = Cli.update(action=action, replacement=RecordedReplacement())

        captured = capsys.readouterr()
        assert code == ExitCode.RELEASE_INCOMPLETE
        assert code not in (ExitCode.OK, ExitCode.LIVE_RUNS, ExitCode.UNSUPPORTED_PLATFORM)
        assert captured.err == "version 0.2.0 does not have all its files yet\n"
        assert captured.out == ""
        assert installation.install_wheel.mock_calls == []

    def test_no_two_exit_codes_share_a_value(self) -> None:
        codes = [member.value for member in ExitCode]

        assert len(codes) == len(set(codes))


class TestTheUpdateThatInstalls(UpdatePorts):
    def test_after_installing_the_wheel_it_relaunches_update_with_the_slice_runner_just_installed(
        self, action: UpdateProgram, installation: Mock
    ) -> None:
        replacement = RecordedReplacement()

        with pytest.raises(ReplacementRequestedError):
            Cli.update(action=action, replacement=replacement)

        installation.install_wheel.assert_called_once()
        assert replacement.argvs == [["/home/someone/.local/bin/slice-runner", "update"]]

    def test_when_the_running_version_is_the_latest_it_completes_without_relaunching(
        self, action: UpdateProgram, installation: Mock
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")

        code = Cli.update(action=action, replacement=MissingExecutableReplacement())

        assert code == ExitCode.OK
        installation.install_binary.assert_called_once()
        installation.install_skills.assert_called_once()


class TestTheCheckOfTheLatestVersion(UpdatePorts):
    def test_a_newer_release_prints_exactly_its_version_with_a_newline_and_succeeds(
        self, query: ReadNewerRelease, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.update_check(query=query, running_program=INSTALLED)

        assert code == ExitCode.OK
        assert capsys.readouterr().out == "0.2.0\n"

    def test_the_latest_being_the_running_one_prints_nothing_and_succeeds(
        self, query: ReadNewerRelease, installation: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        installation.running_version.return_value = ReleaseVersion.of("0.2.0")

        code = Cli.update_check(query=query, running_program=INSTALLED)

        assert code == ExitCode.OK
        assert capsys.readouterr().out == ""

    def test_a_release_that_cannot_be_queried_prints_nothing_and_succeeds(
        self, query: ReadNewerRelease, releases: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        releases.latest.side_effect = UnreadableReleaseError("gh timed out")

        code = Cli.update_check(query=query, running_program=INSTALLED)

        captured = capsys.readouterr()
        assert code == ExitCode.OK
        assert (captured.out, captured.err) == ("", "")


class TestTheUpdateSubcommand:
    def test_the_parser_takes_update_with_and_without_check(self) -> None:
        assert Cli.parser().parse_args(["update"]).check is False
        assert Cli.parser().parse_args(["update", "--check"]).check is True
