from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_mergeability import PullRequestMergeability
    from slice_runner.domain.pull_request_state import PullRequestState


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestStatus:
    state: PullRequestState
    mergeability: PullRequestMergeability
