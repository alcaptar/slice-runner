from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.exceptions import CiCommandFailedError, UnreadableCiError
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.pull_request_mergeability import PullRequestMergeability

if TYPE_CHECKING:
    from slice_runner.domain.ci import Ci
    from slice_runner.domain.forum import Forum


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadCiStatusParams:
    repo: str
    pull_request: int


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadCiStatusResult:
    outcome: Outcome
    indeterminate_cause: CiIndeterminateCause | None = None


class ReadCiStatus:
    def __init__(self, *, ci: Ci, forum: Forum) -> None:
        self._ci = ci
        self._forum = forum

    def execute(self, params: ReadCiStatusParams) -> ReadCiStatusResult:
        try:
            status = self._ci.status(repo=params.repo, pull_request=params.pull_request)
        except (CiCommandFailedError, UnreadableCiError) as unreadable:
            return self._indeterminate(params, cause=CiIndeterminateCause.of_the_failure(unreadable))

        outcome = Outcome.of_the_ci(status)
        if outcome is Outcome.INDETERMINATE:
            return self._indeterminate(params, cause=None)

        return ReadCiStatusResult(outcome=outcome)

    def _indeterminate(self, params: ReadCiStatusParams, *, cause: CiIndeterminateCause | None) -> ReadCiStatusResult:
        status = self._forum.pull_request_state(repo=params.repo, number=params.pull_request)
        if status.mergeability is PullRequestMergeability.CONFLICTING:
            return ReadCiStatusResult(outcome=Outcome.CONFLICTING)

        return ReadCiStatusResult(outcome=Outcome.INDETERMINATE, indeterminate_cause=cause)
