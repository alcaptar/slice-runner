from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Self

from slice_runner.domain.exceptions import UnreadableReleaseError


@dataclass(frozen=True, kw_only=True, slots=True)
class ReleaseVersion:
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")

    numbers: tuple[int, int, int]

    @classmethod
    def of(cls, text: str) -> Self:
        matched = cls.PATTERN.fullmatch(text.strip())
        if matched is None:
            raise UnreadableReleaseError(f"`{text}` is not a version of the form MAJOR.MINOR.PATCH")

        major, minor, patch = (int(group) for group in matched.groups())

        return cls(numbers=(major, minor, patch))

    def is_newer_than(self, other: ReleaseVersion) -> bool:
        return self.numbers > other.numbers

    def __str__(self) -> str:
        return ".".join(str(number) for number in self.numbers)
