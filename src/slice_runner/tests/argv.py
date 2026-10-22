from __future__ import annotations

from itertools import pairwise


class Argv:
    def __init__(self, argv: list[str]) -> None:
        self._argv = argv

    @property
    def executable(self) -> str:
        return self._argv[0]

    def value_of(self, flag: str) -> str:
        values = self.values_of(flag)
        if len(values) != 1:
            raise AssertionError(f"expected exactly one {flag} with a value, found {len(values)}")

        return values[0]

    def values_of(self, flag: str) -> list[str]:
        return [following for previous, following in pairwise(self._argv) if previous == flag]

    def contains(self, flag: str) -> bool:
        return flag in self._argv

    def values_that_follow_another_value(self) -> list[str]:
        return [
            following
            for previous, following in pairwise(self._argv)
            if not following.startswith("-") and not previous.startswith("-")
        ]
