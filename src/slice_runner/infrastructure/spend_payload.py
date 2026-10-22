from __future__ import annotations

from typing import Self

from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.contract_model import ContractModel


class SpendPayload(ContractModel):
    cost_usd: float
    turns: int
    duration_ms: int
    calls: int
    models: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    ttft_ms: int
    duration_api_ms: int

    @classmethod
    def from_domain(cls, spend: HarnessSpend) -> Self:
        return cls(
            cost_usd=spend.cost_usd,
            turns=spend.turns,
            duration_ms=spend.duration_ms,
            calls=spend.calls,
            models=spend.models,
            input_tokens=spend.input_tokens,
            output_tokens=spend.output_tokens,
            cache_creation_tokens=spend.cache_creation_tokens,
            cache_read_tokens=spend.cache_read_tokens,
            ttft_ms=spend.ttft_ms,
            duration_api_ms=spend.duration_api_ms,
        )

    def to_domain(self) -> HarnessSpend:
        return HarnessSpend(
            cost_usd=self.cost_usd,
            turns=self.turns,
            duration_ms=self.duration_ms,
            calls=self.calls,
            models=self.models,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens,
            ttft_ms=self.ttft_ms,
            duration_api_ms=self.duration_api_ms,
        )
