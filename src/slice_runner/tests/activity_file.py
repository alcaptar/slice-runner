from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.slice_coordinates import SliceCoordinates


class ActivityFile:
    @staticmethod
    def path_of(root: Path, coordinates: SliceCoordinates) -> Path:
        return (
            root
            / "slice-runner"
            / "runs"
            / "activity"
            / coordinates.repo
            / str(coordinates.issue)
            / f"{coordinates.slice_id.text}.jsonl"
        )

    @classmethod
    def lines_of(cls, root: Path, coordinates: SliceCoordinates) -> list[dict[str, object]]:
        text = cls.path_of(root, coordinates).read_text(encoding="utf-8")

        return [json.loads(line) for line in text.splitlines()]

    @classmethod
    def what_was_done(cls, root: Path, coordinates: SliceCoordinates) -> list[tuple[object, object, object]]:
        return [(line["actor"], line["tool"], line["target"]) for line in cls.lines_of(root, coordinates)]
