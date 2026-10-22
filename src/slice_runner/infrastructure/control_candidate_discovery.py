from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.control_candidate import ControlCandidate, ControlCandidateSource

if TYPE_CHECKING:
    from pathlib import Path


class ControlCandidateDiscovery:
    MAKEFILE_NAMES: ClassVar[tuple[str, ...]] = ("Makefile", "makefile", "GNUmakefile")
    TARGET: ClassVar[re.Pattern[str]] = re.compile(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)")
    COMMENT: ClassVar[re.Pattern[str]] = re.compile(r"^#+\s*(.*?)\s*$")
    PYPROJECT_SIGNALS: ClassVar[tuple[tuple[str, tuple[str, ...], str], ...]] = (
        ("ruff", ("tool", "ruff"), "ruff check ."),
        ("format", ("tool", "ruff", "format"), "ruff format --check ."),
        ("mypy", ("tool", "mypy"), "mypy ."),
        ("pytest", ("tool", "pytest", "ini_options"), "pytest"),
    )

    @classmethod
    def of(cls, repo_root: Path) -> tuple[ControlCandidate, ...]:
        candidates: list[ControlCandidate] = []

        makefile = next((repo_root / name for name in cls.MAKEFILE_NAMES if (repo_root / name).is_file()), None)
        if makefile is not None:
            candidates.extend(cls._from_the_makefile(makefile))

        pyproject = repo_root / "pyproject.toml"
        if pyproject.is_file():
            candidates.extend(cls._from_the_pyproject(pyproject))

        if (repo_root / "tox.ini").is_file():
            candidates.append(
                ControlCandidate(
                    name="tox", command="tox", source=ControlCandidateSource.TOX, hint="there is a tox.ini"
                )
            )

        return tuple(candidates)

    @classmethod
    def _from_the_makefile(cls, makefile: Path) -> list[ControlCandidate]:
        candidates: list[ControlCandidate] = []
        seen: set[str] = set()
        hint = ""

        for line in makefile.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("\t"):
                continue

            if comment := cls.COMMENT.match(line):
                hint = comment.group(1)
            elif target := cls.TARGET.match(line):
                name = target.group(1)
                if name not in seen:
                    seen.add(name)
                    candidates.append(
                        ControlCandidate(
                            name=name, command=f"make {name}", source=ControlCandidateSource.MAKEFILE, hint=hint
                        )
                    )
                hint = ""
            elif not line.strip():
                hint = ""

        return candidates

    @classmethod
    def _from_the_pyproject(cls, pyproject: Path) -> list[ControlCandidate]:
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            return []

        return [
            ControlCandidate(
                name=name,
                command=command,
                source=ControlCandidateSource.PYPROJECT,
                hint=f"configured in [{'.'.join(path)}]",
            )
            for name, path, command in cls.PYPROJECT_SIGNALS
            if cls._has_the_table(data, path)
        ]

    @staticmethod
    def _has_the_table(data: dict[str, object], path: tuple[str, ...]) -> bool:
        node: object = data
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return False
            node = node[key]

        return True
