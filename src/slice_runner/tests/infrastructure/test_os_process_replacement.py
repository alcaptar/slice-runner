from __future__ import annotations

import pytest

from slice_runner.infrastructure.os_process_replacement import OsProcessReplacement
from slice_runner.infrastructure.process_replacement import ExecutableNotFoundError


class TestReplacingTheProcessWithAnExecutableThatDoesNotExist:
    def test_it_raises_the_error_of_the_port_instead_of_the_one_of_the_operating_system(self) -> None:
        with pytest.raises(ExecutableNotFoundError):
            OsProcessReplacement().replaced_by(["slice-runner-tui-that-is-not-installed-anywhere"])
