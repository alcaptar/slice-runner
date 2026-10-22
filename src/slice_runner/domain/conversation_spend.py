from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, kw_only=True, slots=True)
class ConversationSpend:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @classmethod
    def nothing(cls) -> ConversationSpend:
        return cls()

    @classmethod
    def summing(cls, spends: Iterable[ConversationSpend]) -> ConversationSpend:
        return reduce(cls.plus, spends, cls.nothing())

    def plus(self, other: ConversationSpend) -> ConversationSpend:
        return ConversationSpend(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )
