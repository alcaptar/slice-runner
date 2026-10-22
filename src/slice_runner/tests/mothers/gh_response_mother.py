from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar


class GhResponseMother:
    _DIRECTORY: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads"

    @classmethod
    def parent_with_two_children(cls) -> dict[str, object]:
        data = json.loads((cls._DIRECTORY / "parent-with-two-children.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("the recorded parent payload is not an object")

        return data

    @classmethod
    def children_of_parent(cls) -> list[dict[str, object]]:
        data = json.loads((cls._DIRECTORY / "children-of-parent.json").read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise TypeError("the recorded children payload is not an array")

        return data

    @classmethod
    def pull_request_of_branch(cls) -> list[dict[str, object]]:
        data = json.loads((cls._DIRECTORY / "pull-request-of-branch.json").read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise TypeError("the recorded pull request payload is not an array")

        return data

    @classmethod
    def subissue_comments(cls) -> list[dict[str, object]]:
        data = json.loads((cls._DIRECTORY / "subissue-comments.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("the recorded comments payload is not an object")
        comments = data["comments"]
        if not isinstance(comments, list):
            raise TypeError("the recorded comments payload does not carry an array of comments")

        return comments

    @classmethod
    def sub_issues_of_parent(cls) -> list[dict[str, object]]:
        data = json.loads((cls._DIRECTORY / "sub-issues-of-parent.json").read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise TypeError("the recorded sub_issues payload is not an array")

        return data
