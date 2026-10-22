from __future__ import annotations

from slice_runner.domain.effort import Effort


class TestTheLevelsOfEffortTheHarnessAccepts:
    def test_they_are_exactly_the_five_the_harness_names_in_lowercase(self) -> None:
        assert [str(level) for level in Effort] == ["low", "medium", "high", "xhigh", "max"]
