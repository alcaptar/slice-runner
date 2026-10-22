from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import UnreadableReleaseError
from slice_runner.domain.program_installation import ProgramInstallation
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.infrastructure.installed_version import InstalledVersion
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError

if TYPE_CHECKING:
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.infrastructure.process import Process


class UvProgramInstallation(ProgramInstallation):
    PROGRAM_NAME: ClassVar[str] = "slice-runner"
    BINARY_NAME: ClassVar[str] = "slice-runner-tui"
    EXECUTABLE_MODE: ClassVar[int] = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH

    def __init__(self, *, process: Process, skill_library: SkillLibrary, packaged_skills: Path) -> None:
        self._process = process
        self._skill_library = skill_library
        self._packaged_skills = packaged_skills

    def running_version(self) -> ReleaseVersion:
        return ReleaseVersion.of(InstalledVersion.read())

    def interface_version(self) -> ReleaseVersion | None:
        interface = self._executables() / self.BINARY_NAME
        try:
            output = self._process.run([str(interface), "--version"], stdin="")
            if output.code != 0:
                return None

            return ReleaseVersion.of(output.stdout)
        except (ProcessNotRunnableError, ProcessTimedOutError, UnreadableReleaseError):
            return None

    def installed_program(self) -> Path:
        return self._executables() / self.PROGRAM_NAME

    def install_wheel(self, wheel: Path) -> Path:
        self._uv(["tool", "install", "--force", str(wheel)])

        return self.installed_program()

    def install_binary(self, binary: Path) -> None:
        directory = self._executables()
        handle, temporary = tempfile.mkstemp(dir=directory, prefix=f".{self.BINARY_NAME}-")
        os.close(handle)
        try:
            shutil.copyfile(binary, temporary)
            Path(temporary).chmod(self.EXECUTABLE_MODE)
            os.replace(temporary, directory / self.BINARY_NAME)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def install_skills(self) -> None:
        root = self._skill_library.root() / "skills"
        root.mkdir(parents=True, exist_ok=True)
        for skill in sorted(self._packaged_skills.iterdir()):
            if skill.is_dir():
                self._replaced(root / skill.name, by=skill)

    @staticmethod
    def _replaced(destination: Path, *, by: Path) -> None:
        if destination.is_symlink():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(by, destination)

    def _executables(self) -> Path:
        return Path(self._uv(["tool", "dir", "--bin"]).strip())

    def _uv(self, arguments: list[str]) -> str:
        try:
            output = self._process.run(["uv", *arguments], stdin="")
        except (ProcessNotRunnableError, ProcessTimedOutError) as error:
            raise UnreadableReleaseError(str(error)) from error
        if output.code != 0:
            raise UnreadableReleaseError(output.reason(tool="uv"))

        return output.stdout
