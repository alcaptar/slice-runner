from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import ProcessOutput


class GitCommandFailedError(OSError):
    @classmethod
    def from_command(cls, argv: list[str], output: ProcessOutput) -> Self:
        return cls(f"{' '.join(argv)}: {output.reason(tool=argv[0])}")
