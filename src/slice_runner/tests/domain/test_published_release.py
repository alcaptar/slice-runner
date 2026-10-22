from __future__ import annotations

from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.tests.mothers.published_release_mother import PublishedReleaseMother


class TestPublishedReleaseCarries:
    def test_a_release_with_the_wheel_and_the_binary_of_the_platform_is_complete_for_it(self) -> None:
        assert PublishedReleaseMother.complete().carries(BinaryPlatform.MACOS_ARM64)

    def test_a_release_with_only_the_binary_of_the_other_platform_is_incomplete_for_this_one(self) -> None:
        release = PublishedReleaseMother.without_the_binary_of(platform=BinaryPlatform.MACOS_ARM64)

        assert not release.carries(BinaryPlatform.MACOS_ARM64)
        assert release.carries(BinaryPlatform.LINUX_X86_64)

    def test_a_release_without_the_wheel_is_incomplete_even_with_the_binary(self) -> None:
        assert not PublishedReleaseMother.without_the_wheel().carries(BinaryPlatform.MACOS_ARM64)
