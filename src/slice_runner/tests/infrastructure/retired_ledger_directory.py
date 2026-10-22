from __future__ import annotations

import os
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pathlib import Path


class RetiredLedgerDirectory:
    SEGMENTS: ClassVar[tuple[str, str]] = ("slice-runner", "log")

    @staticmethod
    def path(root: Path, name: str) -> Path:
        return root.joinpath(*RetiredLedgerDirectory.SEGMENTS, f"{name}.jsonl")

    @staticmethod
    def seeded_without_opening(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        try:
            os.write(descriptor, data)
        finally:
            os.close(descriptor)

    @staticmethod
    def read_without_opening(path: Path) -> bytes:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            return os.read(descriptor, 1_000_000)
        finally:
            os.close(descriptor)
