from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Self

from slice_runner.domain.exceptions import MalformedSliceIdError

_CANONICAL = re.compile(r"^.+-\d+$")


@dataclass(frozen=True, kw_only=True, slots=True)
class CanonicalSliceId:
    text: str

    @classmethod
    def of_parts(cls, *, ordinal: int, user_story: str | None) -> Self:
        prefix = "slice" if user_story is None else user_story

        return cls(text=f"{prefix}-{ordinal:02d}")

    @classmethod
    def of_text(cls, text: str) -> Self:
        if not _CANONICAL.match(text):
            raise MalformedSliceIdError(f"`{text}` is not a canonical slice identifier")

        return cls(text=text)

    @property
    def branch_suffix(self) -> str:
        return self.text.removeprefix("slice-")
