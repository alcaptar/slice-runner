from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar


class ClaudeConfig:
    VARIABLE: ClassVar[str] = "CLAUDE_CONFIG_DIR"
    DEFAULT: ClassVar[str] = "~/.claude"

    @classmethod
    def root(cls) -> Path:
        return Path(os.environ.get(cls.VARIABLE) or cls.DEFAULT).expanduser()
