from __future__ import annotations

import pytest

from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.exceptions import UnsupportedPlatformError
from slice_runner.infrastructure.local_host_platform import LocalHostPlatform


class TestThePlatformOfTheHost:
    @pytest.mark.parametrize(
        ("system", "machine", "expected"),
        [
            ("Darwin", "arm64", BinaryPlatform.MACOS_ARM64),
            ("Linux", "x86_64", BinaryPlatform.LINUX_X86_64),
        ],
    )
    def test_the_two_platforms_with_a_published_binary_resolve_to_their_target(
        self, system: str, machine: str, expected: BinaryPlatform
    ) -> None:
        assert LocalHostPlatform(system=system, machine=machine).binary_platform() is expected

    @pytest.mark.parametrize(("system", "machine"), [("Darwin", "x86_64"), ("Linux", "aarch64"), ("Windows", "AMD64")])
    def test_any_other_platform_is_unsupported_and_the_error_names_it(self, system: str, machine: str) -> None:
        with pytest.raises(UnsupportedPlatformError, match=f"{system} {machine}"):
            LocalHostPlatform(system=system, machine=machine).binary_platform()
