from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessSpend:
    cost_usd: float = 0.0
    turns: int = 0
    duration_ms: int = 0
    calls: int = 0
    models: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    ttft_ms: int = 0
    duration_api_ms: int = 0

    @classmethod
    def nothing(cls) -> HarnessSpend:
        return cls()

    @classmethod
    def summing(cls, spends: Iterable[HarnessSpend]) -> HarnessSpend:
        return reduce(cls.plus, spends, cls.nothing())

    @property
    def measured(self) -> bool:
        return self.calls > 0

    def plus(self, other: HarnessSpend) -> HarnessSpend:
        return HarnessSpend(
            cost_usd=self.cost_usd + other.cost_usd,
            turns=self.turns + other.turns,
            duration_ms=self.duration_ms + other.duration_ms,
            calls=self.calls + other.calls,
            models=tuple(sorted(set(self.models) | set(other.models))),
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            ttft_ms=self.ttft_ms + other.ttft_ms,
            duration_api_ms=self.duration_api_ms + other.duration_api_ms,
        )
