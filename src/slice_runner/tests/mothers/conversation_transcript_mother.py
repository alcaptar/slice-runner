from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar


class ConversationTranscriptMother:
    SESSION: ClassVar[str] = "779e530f-c285-495c-bbdc-f2896f81fe25"
    REJECTED_STRUCTURED_OUTPUT: ClassVar[str] = "conversation-with-a-rejected-structured-output"
    WORKTREE: ClassVar[str] = "/repos/acme.orders.api/.claude/worktrees/the-slice"
    PROJECT_DIRECTORY: ClassVar[str] = "-repos-acme-orders-api--claude-worktrees-the-slice"

    _PAYLOADS: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads"

    @classmethod
    def written_under(cls, root: Path, *, recorded: str = "conversation-turns") -> None:
        cls.destination_of(root, session=cls.SESSION).write_text(
            (cls._PAYLOADS / f"{recorded}.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
        )

    @classmethod
    def written_for_the_directory(cls, root: Path, *, directory: Path) -> None:
        destination = root / "projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(directory)) / f"{cls.SESSION}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            (cls._PAYLOADS / "conversation-turns.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
        )

    @classmethod
    def destination_of(cls, root: Path, *, session: str) -> Path:
        destination = root / "projects" / cls.PROJECT_DIRECTORY / f"{session}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)

        return destination
