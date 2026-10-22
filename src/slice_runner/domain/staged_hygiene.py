from __future__ import annotations

from pathlib import PurePosixPath

from slice_runner.domain.hygiene_breach import HygieneBreach
from slice_runner.domain.hygiene_offence import HygieneOffence


class StagedHygiene:
    @classmethod
    def of(cls, *, staged: tuple[str, ...], declared: tuple[str, ...]) -> tuple[HygieneOffence, ...]:
        allowed = {cls._normalized(path) for path in declared}
        offences = (cls._offence(cls._normalized(path), allowed) for path in staged)

        return tuple(offence for offence in offences if offence is not None)

    @staticmethod
    def _offence(path: str, allowed: set[str]) -> HygieneOffence | None:
        if path not in allowed:
            return HygieneOffence(path=path, breach=HygieneBreach.NOT_DECLARED)

        return None

    @staticmethod
    def _normalized(path: str) -> str:
        return PurePosixPath(path).as_posix()
