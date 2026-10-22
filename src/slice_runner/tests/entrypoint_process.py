from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.tests.doubles import AnsweringByArgv

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class EntrypointProcess:
    LOCAL_PROCESS: str = "slice_runner.infrastructure.cli.LocalProcess"

    @classmethod
    def answering_with(cls, monkeypatch: pytest.MonkeyPatch, process: Process) -> None:
        monkeypatch.setattr(cls.LOCAL_PROCESS, lambda **_: process)


class WithTheEntrypointLaunchingNothing:
    @pytest.fixture(autouse=True)
    def entrypoint_process(self, monkeypatch: pytest.MonkeyPatch) -> AnsweringByArgv:
        process = AnsweringByArgv()
        EntrypointProcess.answering_with(monkeypatch, process)

        return process
