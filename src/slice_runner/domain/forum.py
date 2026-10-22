from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.branch_pull_request import BranchPullRequest
    from slice_runner.domain.pull_request_review import PullRequestReview
    from slice_runner.domain.pull_request_status import PullRequestStatus


class Forum(ABC):
    @abstractmethod
    def open_pull_request(self, *, repo: str, branch: str) -> int | None: ...

    @abstractmethod
    def open_pull_requests(self, *, repo: str, branches: tuple[str, ...]) -> tuple[BranchPullRequest, ...]: ...

    @abstractmethod
    def any_pull_request(self, *, repo: str, branch: str) -> int | None: ...

    @abstractmethod
    def create_pull_request(self, *, repo: str, branch: str, base: str, title: str, body: str) -> int: ...

    @abstractmethod
    def pull_request_state(self, *, repo: str, number: int) -> PullRequestStatus: ...

    @abstractmethod
    def reviews(self, *, repo: str, pull_request: int) -> tuple[PullRequestReview, ...]: ...

    @abstractmethod
    def authenticated_as(self) -> str | None: ...

    @abstractmethod
    def can_read(self, *, repo: str) -> bool: ...
