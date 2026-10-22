from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceCommitMessage:
    CO_AUTHOR: ClassVar[str] = "Co-Authored-By: Claude <noreply@anthropic.com>"

    subject: str
    round: int

    def rendered(self) -> str:
        return "\n".join([self._subject_of_the_round(), "", self.CO_AUTHOR])

    def _subject_of_the_round(self) -> str:
        if self.round == 1:
            return self.subject

        return f"{self.subject} (vuelta {self.round})"
