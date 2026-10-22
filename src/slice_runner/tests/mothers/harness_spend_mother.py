from __future__ import annotations

from slice_runner.domain.harness_spend import HarnessSpend


class HarnessSpendMother:
    @staticmethod
    def of_the_implementer_call() -> HarnessSpend:
        return HarnessSpend(
            cost_usd=0.3433209,
            turns=9,
            duration_ms=36315,
            calls=1,
            models=("claude-sonnet-5",),
            input_tokens=13,
            output_tokens=1159,
            cache_creation_tokens=42251,
            cache_read_tokens=241303,
            ttft_ms=5588,
            duration_api_ms=32189,
        )

    @staticmethod
    def of_the_judge_call() -> HarnessSpend:
        return HarnessSpend(
            cost_usd=0.051877,
            turns=5,
            duration_ms=29337,
            calls=1,
            models=("claude-haiku-4-5-20251001",),
            input_tokens=17,
            output_tokens=3443,
            cache_creation_tokens=16547,
            cache_read_tokens=15510,
            ttft_ms=5384,
            duration_api_ms=28905,
        )

    @staticmethod
    def of_the_understanding_call() -> HarnessSpend:
        return HarnessSpend(
            cost_usd=0.021415, turns=3, duration_ms=14208, calls=1, models=("claude-sonnet-5",), cache_read_tokens=42066
        )

    @staticmethod
    def of_a_call_that_cost_nothing() -> HarnessSpend:
        return HarnessSpend(calls=1, models=("claude-haiku-4-5-20251001",))
