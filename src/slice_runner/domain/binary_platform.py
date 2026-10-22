from __future__ import annotations

from enum import StrEnum
from typing import Self

from slice_runner.domain.exceptions import UnsupportedPlatformError


class BinaryPlatform(StrEnum):
    MACOS_ARM64 = "aarch64-apple-darwin"
    LINUX_X86_64 = "x86_64-unknown-linux-gnu"

    @classmethod
    def of(cls, *, system: str, machine: str) -> Self:
        match (system, machine):
            case ("Darwin", "arm64"):
                return cls.MACOS_ARM64
            case ("Linux", "x86_64"):
                return cls.LINUX_X86_64
            case _:
                raise UnsupportedPlatformError(f"{system} {machine} has no published binary of the interface")
