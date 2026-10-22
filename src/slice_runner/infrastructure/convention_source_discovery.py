from __future__ import annotations

import os
import re
from pathlib import Path
from typing import ClassVar

from slice_runner.domain.source import Source, SourceKind


class ConventionSourceDiscovery:
    NOISE_DIRECTORIES: ClassVar[frozenset[str]] = frozenset(
        {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".mypy_cache",
            ".ruff_cache",
            ".pytest_cache",
            "dist",
            "build",
            ".idea",
            ".tox",
            ".eggs",
        }
    )
    DOCUMENT_FILENAMES: ClassVar[frozenset[str]] = frozenset({"CLAUDE.md", "AGENTS.md", "GEMINI.md"})
    CONTRIBUTING: ClassVar[re.Pattern[str]] = re.compile(r"^contributing(\.md|\.rst|\.txt)?$", re.IGNORECASE)
    CONVENTION_DIRECTORY: ClassVar[re.Pattern[str]] = re.compile(r"(convention|rules)", re.IGNORECASE)
    SKILLS_DIRECTORY: ClassVar[str] = ".claude/skills"

    @classmethod
    def of(cls, repo_root: Path) -> tuple[Source, ...]:
        documents: set[str] = set()
        skills: set[str] = set()
        convention_directories: list[str] = []

        for directory, subdirectories, filenames in os.walk(repo_root):
            subdirectories[:] = sorted(name for name in subdirectories if name not in cls.NOISE_DIRECTORIES)
            here = Path(directory)
            relative_here = here.relative_to(repo_root).as_posix()

            if cls._is_a_skills_directory(relative_here):
                skills.update(f"{relative_here}/{name}/" for name in subdirectories if not name.startswith("."))

            if relative_here != "." and cls.CONVENTION_DIRECTORY.search(here.name):
                convention_directories.append(f"{relative_here}/")

            documents.update(
                (here / filename).relative_to(repo_root).as_posix()
                for filename in filenames
                if filename in cls.DOCUMENT_FILENAMES or cls.CONTRIBUTING.match(filename)
            )

        documents.update(cls._outermost(convention_directories))

        return tuple(
            Source(kind=kind, path=path)
            for kind, paths in ((SourceKind.DOC, documents), (SourceKind.SKILL, skills))
            for path in sorted(paths)
        )

    @classmethod
    def _is_a_skills_directory(cls, relative_path: str) -> bool:
        return relative_path == cls.SKILLS_DIRECTORY or relative_path.endswith(f"/{cls.SKILLS_DIRECTORY}")

    @staticmethod
    def _outermost(directories: list[str]) -> list[str]:
        unique = sorted(set(directories))

        return [
            directory
            for directory in unique
            if not any(directory != other and directory.startswith(other) for other in unique)
        ]
