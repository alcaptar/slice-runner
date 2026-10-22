from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.clock import Clock
from slice_runner.infrastructure.claude_config import ClaudeConfig

if TYPE_CHECKING:
    from pathlib import Path


class WithTheDurableStoresOutOfTheRealHome:
    STAMP: ClassVar[datetime] = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)

    @pytest.fixture(autouse=True)
    def durable_store_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @classmethod
    def frozen_at(cls, stamp: datetime | None = None) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = stamp if stamp is not None else cls.STAMP

        return clock
