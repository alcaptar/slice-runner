from __future__ import annotations

from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.host_platform import HostPlatform


class LocalHostPlatform(HostPlatform):
    def __init__(self, *, system: str, machine: str) -> None:
        self._system = system
        self._machine = machine

    def binary_platform(self) -> BinaryPlatform:
        return BinaryPlatform.of(system=self._system, machine=self._machine)
