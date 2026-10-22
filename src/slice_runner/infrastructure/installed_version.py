from __future__ import annotations

from importlib import metadata
from typing import ClassVar

from slice_runner.domain.program_version import ProgramVersion


class InstalledVersion(ProgramVersion):
    DISTRIBUTION: ClassVar[str] = "slice-runner"

    @classmethod
    def read(cls) -> str:
        return metadata.version(cls.DISTRIBUTION)
