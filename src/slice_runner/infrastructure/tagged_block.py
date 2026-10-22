from __future__ import annotations

import hashlib
from typing import ClassVar


class TaggedBlock:
    IDENTIFIER_LENGTH: ClassVar[int] = 8

    @classmethod
    def of(cls, tag: str, content: str) -> str:
        identifier = hashlib.sha256(content.encode("utf-8")).hexdigest()[: cls.IDENTIFIER_LENGTH]

        return f'<{tag} id="{identifier}">\n{content}\n</{tag} id="{identifier}">'
