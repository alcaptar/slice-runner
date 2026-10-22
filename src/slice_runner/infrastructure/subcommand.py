from __future__ import annotations

from enum import StrEnum


class Subcommand(StrEnum):
    VERIFY = "verify"
    EXPLAIN = "explain"
    RUN = "run"
    READ = "read"
    SPEND = "spend"
    DOCTOR = "doctor"
    METRICS = "metrics"
    RESET = "reset"
    STATUS = "status"
    FOLLOW = "follow"
    RETRY = "retry"
    TUI = "tui"
    REGISTER = "register"
    DISCOVER_CONVENTIONS = "discover-conventions"
    DISCOVER_CONTROLS = "discover-controls"
    UPDATE = "update"
