from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from slice_runner.infrastructure.system_clock import SystemClock

if TYPE_CHECKING:
    import pytest


class TestSystemClock:
    def test_the_seconds_it_is_asked_to_wait_reach_the_system_call_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        slept: list[float] = []
        monkeypatch.setattr("time.sleep", slept.append)

        SystemClock().sleep(seconds=30)

        assert slept == [30]

    def test_the_instant_it_reports_is_timezone_aware_and_close_to_the_moment_it_was_asked(self) -> None:
        before = datetime.now(UTC)

        reported = SystemClock().now()

        after = datetime.now(UTC)
        assert before <= reported <= after
