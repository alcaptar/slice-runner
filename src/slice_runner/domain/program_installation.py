from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.release_version import ReleaseVersion


class ProgramInstallation(ABC):
    @abstractmethod
    def running_version(self) -> ReleaseVersion: ...

    @abstractmethod
    def interface_version(self) -> ReleaseVersion | None: ...

    @abstractmethod
    def installed_program(self) -> Path: ...

    @abstractmethod
    def install_wheel(self, wheel: Path) -> Path: ...

    @abstractmethod
    def install_binary(self, binary: Path) -> None: ...

    @abstractmethod
    def install_skills(self) -> None: ...
