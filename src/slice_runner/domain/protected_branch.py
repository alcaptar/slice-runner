from __future__ import annotations

from enum import StrEnum


class ProtectedBranch(StrEnum):
    MASTER = "master"
    MAIN = "main"

    @classmethod
    def protects(cls, name: str) -> bool:
        return any(name == branch.value for branch in cls)
