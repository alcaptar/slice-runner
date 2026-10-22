from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.child_issues import ChildIssues
from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.infrastructure.gh_child_issue_payload import GhChildIssuePayload
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError

if TYPE_CHECKING:
    from slice_runner.domain.child_issue import ChildIssue
    from slice_runner.infrastructure.gh_call import GhCall


class GhChildIssues(ChildIssues):
    def __init__(self, *, call: GhCall) -> None:
        self._call = call

    def of_parent(self, *, repo: str, parent: int) -> tuple[ChildIssue, ...]:
        argv = ["gh", "api", "--paginate", f"repos/{repo}/issues/{parent}/sub_issues"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return tuple(GhChildIssuePayload.from_dict(entry).to_domain() for entry in self._entries(outcome.output.stdout))

    @staticmethod
    def _entries(stdout: str) -> list[dict[str, object]]:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise UnreadableIssueError(f"gh did not return JSON: {error}") from error
        if not isinstance(data, list):
            raise UnreadableIssueError(f"gh has to return an array, not {type(data).__name__}")

        return data
