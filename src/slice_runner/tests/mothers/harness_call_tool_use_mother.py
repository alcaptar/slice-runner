from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, ToolUse


class HarnessCallToolUseMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ISSUE: ClassVar[int] = 11
    SLICE_ID: ClassVar[str] = "slice-11"
    SESSION: ClassVar[str] = "779e530f-c285-495c-bbdc-f2896f81fe25"

    LONG_COMMAND: ClassVar[str] = (
        "git commit -m \"$(cat <<'EOF'\n"
        + "\n".join(f"line {number} of a long commit message" + " padding" * 20 for number in range(100))
        + '\nEOF\n)"'
    )

    @classmethod
    def coordinates(cls) -> SliceCoordinates:
        return SliceCoordinates(repo=cls.REPO, issue=cls.ISSUE, slice_id=CanonicalSliceId.of_text(cls.SLICE_ID))

    @classmethod
    def of_the_implementer(cls) -> HarnessCallToolUse:
        return HarnessCallToolUse(
            coordinates=cls.coordinates(),
            step=Step.IMPLEMENT,
            session=cls.SESSION,
            uses=(
                ToolUse(turn=1, tool="Read", path="src/x.py", command=None),
                ToolUse(turn=2, tool="Bash", path=None, command="make check"),
            ),
        )

    @classmethod
    def of_the_implementer_with_a_long_command(cls) -> HarnessCallToolUse:
        return HarnessCallToolUse(
            coordinates=cls.coordinates(),
            step=Step.IMPLEMENT,
            session=cls.SESSION,
            uses=(ToolUse(turn=1, tool="Bash", path=None, command=cls.LONG_COMMAND),),
        )

    @classmethod
    def of_the_implementer_with_a_failure(cls) -> HarnessCallToolUse:
        return HarnessCallToolUse(
            coordinates=cls.coordinates(),
            step=Step.IMPLEMENT,
            session=cls.SESSION,
            uses=(ToolUse(turn=1, tool="Bash", path=None, command="make check", failed=True),),
        )
