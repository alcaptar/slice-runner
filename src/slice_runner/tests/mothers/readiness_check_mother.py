from __future__ import annotations

from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.readiness_check import ReadinessCheck


class ReadinessCheckMother:
    @staticmethod
    def ready(*, name: str = "git", detail: str = "2.51.0") -> ReadinessCheck:
        return ReadinessCheck(name=name, verdict=CheckVerdict.READY, detail=detail)

    @staticmethod
    def missing(
        *, name: str = "git", detail: str = "not found on the PATH", fix: str = "install git"
    ) -> ReadinessCheck:
        return ReadinessCheck(name=name, verdict=CheckVerdict.MISSING, detail=detail, fix=fix)

    @staticmethod
    def warning(
        *, name: str = "base", detail: str = "master is 1 commit(s) behind its remote", fix: str = "git fetch"
    ) -> ReadinessCheck:
        return ReadinessCheck(name=name, verdict=CheckVerdict.WARNING, detail=detail, fix=fix)

    @staticmethod
    def unknown(*, name: str = "version", detail: str = "could not be read") -> ReadinessCheck:
        return ReadinessCheck(name=name, verdict=CheckVerdict.UNKNOWN, detail=detail)
