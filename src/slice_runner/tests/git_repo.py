from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pathlib import Path


class Git:
    BASE_BRANCH: ClassVar[str] = "master"
    TIMEOUT_SECONDS: ClassVar[int] = 60

    @staticmethod
    def run(repo: Path, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=Git.TIMEOUT_SECONDS,
        )

        return done.stdout

    @classmethod
    def init_repo(cls, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        cls.run(root, "init", "-b", cls.BASE_BRANCH)

        return cls._identified(root)

    @classmethod
    def clone(cls, *, remote: Path, into: Path) -> Path:
        cls.run(into.parent, "clone", str(remote), str(into))

        return cls._identified(into)

    @classmethod
    def _identified(cls, root: Path) -> Path:
        cls.run(root, "config", "user.email", "t@example.com")
        cls.run(root, "config", "user.name", "test")

        return root
