from __future__ import annotations

from typing import ClassVar


class AutomationMark:
    TEXT: ClassVar[str] = "*Comentario automatico de `slice-runner`, no de una persona.*"

    @classmethod
    def appended_to(cls, body: str) -> str:
        return "\n\n".join([body, cls.TEXT])
