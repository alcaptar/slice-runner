from __future__ import annotations

import os
import stat
from importlib import metadata
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadableReleaseError
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_skill_library import LocalSkillLibrary
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError
from slice_runner.infrastructure.uv_program_installation import UvProgramInstallation
from slice_runner.tests.doubles import Answer, AnsweringByArgv, AnsweringByArgvRaisingOn

if TYPE_CHECKING:
    from pathlib import Path


class InstallationOver:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.claude = tmp_path / "claude"
        self.skills = tmp_path / "packaged-skills"
        (self.skills / "slice-spec" / "references").mkdir(parents=True)
        (self.skills / "slice-spec" / "SKILL.md").write_text("packaged", encoding="utf-8")
        (self.skills / "slice-spec" / "references" / "format.md").write_text("reference", encoding="utf-8")
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(self.claude))
        self.process = AnsweringByArgv(
            Answer(to=("uv", "tool", "dir", "--bin"), stdout=f"{self.bin}\n"),
            Answer(to=("uv", "tool", "install")),
        )
        self.installation = UvProgramInstallation(
            process=self.process, skill_library=LocalSkillLibrary(), packaged_skills=self.skills
        )


class InstallationFixtures:
    @pytest.fixture
    def over(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> InstallationOver:
        return InstallationOver(tmp_path, monkeypatch)


class TestTheRunningVersion(InstallationFixtures):
    def test_it_is_the_version_of_the_installed_distribution(self, over: InstallationOver) -> None:
        assert over.installation.running_version() == ReleaseVersion.of(metadata.version("slice-runner"))


class TestTheWheel(InstallationFixtures):
    def test_it_is_installed_with_uv_forcing_the_replacement_of_the_tool(
        self, over: InstallationOver, tmp_path: Path
    ) -> None:
        wheel = tmp_path / "slice_runner-0.2.0-py3-none-any.whl"

        over.installation.install_wheel(wheel)

        assert over.process.ran("uv", "tool", "install", "--force", str(wheel))

    def test_it_answers_with_the_absolute_path_of_the_program_in_the_directory_uv_reports_not_its_bare_name(
        self, over: InstallationOver, tmp_path: Path
    ) -> None:
        program = over.installation.install_wheel(tmp_path / "slice_runner-0.2.0-py3-none-any.whl")

        assert program == over.bin / "slice-runner"

    def test_a_failing_uv_stops_the_update_with_its_reason(self, over: InstallationOver, tmp_path: Path) -> None:
        failing = UvProgramInstallation(
            process=AnsweringByArgv(Answer(to=("uv", "tool", "install"), code=2, stderr="no matching distribution")),
            skill_library=LocalSkillLibrary(),
            packaged_skills=over.skills,
        )

        with pytest.raises(UnreadableReleaseError, match="no matching distribution"):
            failing.install_wheel(tmp_path / "x.whl")


class TestTheBinary(InstallationFixtures):
    @staticmethod
    def _downloaded(tmp_path: Path, content: str) -> Path:
        binary = tmp_path / "downloads" / "slice-runner-tui-aarch64-apple-darwin"
        binary.parent.mkdir()
        binary.write_text(content, encoding="utf-8")

        return binary

    def test_it_lands_executable_under_its_own_name_in_the_directory_uv_reports(
        self, over: InstallationOver, tmp_path: Path
    ) -> None:
        over.installation.install_binary(self._downloaded(tmp_path, "new interface"))

        installed = over.bin / "slice-runner-tui"
        assert installed.read_text(encoding="utf-8") == "new interface"
        assert installed.stat().st_mode & stat.S_IXUSR

    def test_it_is_written_to_a_temporary_file_of_the_same_directory_and_renamed_over_the_old_one(
        self, over: InstallationOver, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (over.bin / "slice-runner-tui").write_text("old interface", encoding="utf-8")
        renames: list[tuple[str, str]] = []
        real_replace = os.replace

        def recording(source: str, destination: str) -> None:
            renames.append((os.path.dirname(source), os.path.dirname(destination)))
            assert (over.bin / "slice-runner-tui").read_text(encoding="utf-8") == "old interface"
            real_replace(source, destination)

        monkeypatch.setattr(os, "replace", recording)

        over.installation.install_binary(self._downloaded(tmp_path, "new interface"))

        assert renames == [(str(over.bin), str(over.bin))]
        assert [entry.name for entry in over.bin.iterdir()] == ["slice-runner-tui"]


class TestTheSkills(InstallationFixtures):
    def test_each_packaged_skill_is_copied_whole_under_the_skills_of_the_claude_folder(
        self, over: InstallationOver
    ) -> None:
        over.installation.install_skills()

        copied = over.claude / "skills" / "slice-spec"
        assert (copied / "SKILL.md").read_text(encoding="utf-8") == "packaged"
        assert (copied / "references" / "format.md").read_text(encoding="utf-8") == "reference"
        assert not copied.is_symlink()

    def test_a_symlink_in_its_place_is_replaced_by_the_copy_and_the_target_of_the_link_stays_intact(
        self, over: InstallationOver, tmp_path: Path
    ) -> None:
        other_clone = tmp_path / "other-clone" / "slice-spec"
        other_clone.mkdir(parents=True)
        (other_clone / "SKILL.md").write_text("edited in another clone", encoding="utf-8")
        link = over.claude / "skills" / "slice-spec"
        link.parent.mkdir(parents=True)
        link.symlink_to(other_clone)

        over.installation.install_skills()

        assert not link.is_symlink()
        assert (link / "SKILL.md").read_text(encoding="utf-8") == "packaged"
        assert [entry.name for entry in other_clone.iterdir()] == ["SKILL.md"]
        assert (other_clone / "SKILL.md").read_text(encoding="utf-8") == "edited in another clone"

    def test_a_copy_from_an_earlier_version_is_replaced_without_leaving_files_that_the_new_one_lacks(
        self, over: InstallationOver
    ) -> None:
        stale = over.claude / "skills" / "slice-spec" / "references" / "retired.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("old", encoding="utf-8")

        over.installation.install_skills()

        assert not stale.exists()
        assert (over.claude / "skills" / "slice-spec" / "SKILL.md").exists()

    def test_skills_of_the_claude_folder_that_the_wheel_does_not_carry_are_left_alone(
        self, over: InstallationOver
    ) -> None:
        mine = over.claude / "skills" / "mine" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("mine", encoding="utf-8")

        over.installation.install_skills()

        assert mine.read_text(encoding="utf-8") == "mine"


class TestTheInstalledProgram(InstallationFixtures):
    def test_it_is_the_slice_runner_inside_the_uv_tool_bin_directory(self, over: InstallationOver) -> None:
        assert over.installation.installed_program() == over.bin / "slice-runner"

    def test_uv_failing_to_resolve_the_directory_raises_with_its_reason(self, over: InstallationOver) -> None:
        installation = UvProgramInstallation(
            process=AnsweringByArgv(Answer(to=("uv", "tool", "dir", "--bin"), code=2, stderr="uv is broken")),
            skill_library=LocalSkillLibrary(),
            packaged_skills=over.skills,
        )

        with pytest.raises(UnreadableReleaseError, match="uv is broken"):
            installation.installed_program()


class TestTheInterfaceVersion(InstallationFixtures):
    @staticmethod
    def _interface(over: InstallationOver) -> str:
        return str(over.bin / "slice-runner-tui")

    @classmethod
    def _printing(cls, over: InstallationOver, *, stdout: str, code: int = 0) -> UvProgramInstallation:
        return UvProgramInstallation(
            process=AnsweringByArgv(
                Answer(to=("uv", "tool", "dir", "--bin"), stdout=f"{over.bin}\n"),
                Answer(to=(cls._interface(over), "--version"), stdout=stdout, code=code),
            ),
            skill_library=LocalSkillLibrary(),
            packaged_skills=over.skills,
        )

    @classmethod
    def _failing(cls, over: InstallationOver, error: Exception) -> UvProgramInstallation:
        return UvProgramInstallation(
            process=AnsweringByArgvRaisingOn(
                Answer(to=("uv", "tool", "dir", "--bin"), stdout=f"{over.bin}\n"),
                when=(cls._interface(over), "--version"),
                raises=error,
            ),
            skill_library=LocalSkillLibrary(),
            packaged_skills=over.skills,
        )

    def test_it_is_the_version_the_interface_executable_of_the_uv_bin_directory_prints(
        self, over: InstallationOver
    ) -> None:
        assert self._printing(over, stdout="0.3.0\n").interface_version() == ReleaseVersion.of("0.3.0")

    def test_an_interface_executable_that_does_not_exist_has_no_version(self, over: InstallationOver) -> None:
        installation = self._failing(over, ProcessNotRunnableError("no such file"))

        assert installation.interface_version() is None

    def test_an_interface_that_exits_with_a_nonzero_code_has_no_version(self, over: InstallationOver) -> None:
        assert self._printing(over, stdout="0.3.0\n", code=1).interface_version() is None

    def test_an_interface_that_exhausts_its_budget_has_no_version(self, over: InstallationOver) -> None:
        installation = self._failing(over, ProcessTimedOutError("timed out"))

        assert installation.interface_version() is None

    def test_an_interface_whose_output_is_not_a_version_has_no_version(self, over: InstallationOver) -> None:
        assert self._printing(over, stdout="slice-runner-tui help\n").interface_version() is None
