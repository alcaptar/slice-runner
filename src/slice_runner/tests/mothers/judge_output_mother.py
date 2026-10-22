from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar


class JudgeVerdictMother:
    @staticmethod
    def passing() -> dict[str, object]:
        return {"ruling": "PASS", "findings": []}

    @staticmethod
    def failing(*findings: dict[str, object]) -> dict[str, object]:
        return {"ruling": "FAIL", "findings": list(findings) or [JudgeVerdictMother.high_severity_finding()]}

    @staticmethod
    def passing_with(*findings: dict[str, object]) -> dict[str, object]:
        return {"ruling": "PASS", "findings": list(findings)}

    @staticmethod
    def high_severity_finding(*, path: str = "src/x.py") -> dict[str, object]:
        return {
            "rule": "boundaries",
            "path": path,
            "severity": "high",
            "evidence": "requests in the domain",
            "detail": "I/O goes behind a port",
        }

    @staticmethod
    def medium_severity_finding(*, path: str = "src/x.py") -> dict[str, object]:
        return JudgeVerdictMother.high_severity_finding(path=path) | {"severity": "medium"}

    @staticmethod
    def low_severity_finding(*, path: str = "src/x.py") -> dict[str, object]:
        return JudgeVerdictMother.high_severity_finding(path=path) | {"severity": "low"}


class HarnessEnvelopeMother:
    JUDGE_RECORDED: ClassVar[tuple[str, ...]] = ("full-recipe", "unbounded-tools")
    ALL_RECORDED: ClassVar[tuple[str, ...]] = (*JUDGE_RECORDED, "implementer-two-paths")

    SESSION_OF_THE_JUDGE: ClassVar[str] = "721332c7-007c-4eb4-9c21-5b29b78de64e"
    SESSION_OF_THE_IMPLEMENTER: ClassVar[str] = "cd8b5450-595b-403e-b6a6-a1f2c9af512c"

    DENIED_READ: ClassVar[str] = (
        "/Users/someone/.claude/plugins/cache/examples/python-practices/2.0.2/skills/"
        "best-practices/references/code-style.md"
    )
    DENIALS_AS_THE_HARNESS_SENDS_THEM: ClassVar[tuple[dict[str, object], ...]] = (
        {
            "tool_name": "Read",
            "tool_use_id": "toolu_0144pjK1fnAQrn8fSEFV9sZA",
            "tool_input": {"file_path": DENIED_READ, "limit": 1},
        },
    )

    _DIRECTORY: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads"

    @classmethod
    def recorded(cls, name: str = "full-recipe") -> dict[str, object]:
        data = json.loads((cls._DIRECTORY / f"{name}.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"the recorded payload {name} is not an object")

        return data

    @classmethod
    def streamed(cls, name: str = "implementer-streamed") -> str:
        return (cls._DIRECTORY / f"{name}.jsonl").read_text(encoding="utf-8")

    @classmethod
    def streamed_then_a_background_task_ends(cls, name: str = "implementer-streamed") -> str:
        notification = json.dumps({"task_id": "b5wtvyehs", "tool_use_id": "toolu_01ABC", "status": "completed"})

        return f"{cls.streamed(name).rstrip()}\n{notification}\n"

    @classmethod
    def carrying(cls, verdict: dict[str, object], *, recorded: str = "full-recipe") -> dict[str, object]:
        return cls.recorded(recorded) | {"structured_output": verdict}

    @classmethod
    def plus(cls, **keys: object) -> dict[str, object]:
        return cls.recorded() | keys

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.recorded().items() if name != key}

    @classmethod
    def without_structured_output(cls, *, recorded: str = "full-recipe") -> dict[str, object]:
        return cls.recorded(recorded) | {"structured_output": None}

    @classmethod
    def without_structured_output_that_ran_out_of_turns(cls, *, recorded: str = "full-recipe") -> dict[str, object]:
        return cls.without_structured_output(recorded=recorded) | {"subtype": "error_max_turns"}

    @classmethod
    def denying_a_read(cls, verdict: dict[str, object] | None = None) -> dict[str, object]:
        return cls.carrying(verdict or JudgeVerdictMother.passing()) | {
            "permission_denials": [dict(denial) for denial in cls.DENIALS_AS_THE_HARNESS_SENDS_THEM]
        }

    @classmethod
    def denying_a_read_over(cls, recorded: str) -> dict[str, object]:
        return cls.recorded(recorded) | {
            "permission_denials": [dict(denial) for denial in cls.DENIALS_AS_THE_HARNESS_SENDS_THEM]
        }
