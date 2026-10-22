from __future__ import annotations

import os
from typing import NoReturn

from slice_runner.infrastructure.process_replacement import ExecutableNotFoundError, ProcessReplacement


class OsProcessReplacement(ProcessReplacement):
    def replaced_by(self, argv: list[str]) -> NoReturn:
        try:
            os.execvp(argv[0], argv)
        except FileNotFoundError as error:
            raise ExecutableNotFoundError(f"{argv[0]} is not on the PATH") from error
