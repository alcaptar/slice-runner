from __future__ import annotations

from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge


class TestNoToolsetChangedWhenSourcesStartedCarryingTheirContent:
    def test_the_implementer_still_gets_the_tools_it_needs_to_read_the_repo_and_run_its_cycle(self) -> None:
        assert SliceImplementerBrief.TOOLS == ("Read", "Write", "Edit", "Bash", "Grep", "Glob", "Skill")

    def test_the_judge_still_gets_only_the_reading_tools(self) -> None:
        assert SliceVerifierJudge.TOOLS == ("Read", "Grep", "Glob", "Skill")
