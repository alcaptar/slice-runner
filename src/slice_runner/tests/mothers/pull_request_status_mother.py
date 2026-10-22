from __future__ import annotations

from slice_runner.domain.pull_request_mergeability import PullRequestMergeability
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.pull_request_status import PullRequestStatus


class PullRequestStatusMother:
    @classmethod
    def merged(cls) -> PullRequestStatus:
        return PullRequestStatus(state=PullRequestState.MERGED, mergeability=PullRequestMergeability.MERGEABLE)

    @classmethod
    def open_and_mergeable(cls) -> PullRequestStatus:
        return PullRequestStatus(state=PullRequestState.OPEN, mergeability=PullRequestMergeability.MERGEABLE)

    @classmethod
    def open_and_conflicting(cls) -> PullRequestStatus:
        return PullRequestStatus(state=PullRequestState.OPEN, mergeability=PullRequestMergeability.CONFLICTING)

    @classmethod
    def closed(cls) -> PullRequestStatus:
        return PullRequestStatus(state=PullRequestState.CLOSED, mergeability=PullRequestMergeability.UNKNOWN)
