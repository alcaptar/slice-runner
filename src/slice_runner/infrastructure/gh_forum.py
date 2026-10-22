from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.forum import Forum
from slice_runner.infrastructure.gh_pull_request_payload import (
    GhPullRequestBranchPayload,
    GhPullRequestPayload,
    GhPullRequestStatePayload,
)
from slice_runner.infrastructure.gh_pull_request_review_payload import (
    GhPullRequestReviewCommentPayload,
    GhPullRequestReviewPayload,
)
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError

if TYPE_CHECKING:
    from slice_runner.domain.branch_pull_request import BranchPullRequest
    from slice_runner.domain.pull_request_review import PullRequestReview
    from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment
    from slice_runner.domain.pull_request_status import PullRequestStatus
    from slice_runner.infrastructure.gh_call import GhCall


class GhForum(Forum):
    def __init__(self, *, call: GhCall) -> None:
        self._call = call

    def open_pull_request(self, *, repo: str, branch: str) -> int | None:
        return self._listed(repo=repo, branch=branch, state="open")

    def any_pull_request(self, *, repo: str, branch: str) -> int | None:
        return self._listed(repo=repo, branch=branch, state="all")

    def open_pull_requests(self, *, repo: str, branches: tuple[str, ...]) -> tuple[BranchPullRequest, ...]:
        argv = ["gh", "pr", "list", "--repo", repo, "--state", "open", "--json", "number,headRefName"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        pulls = (
            GhPullRequestBranchPayload.from_dict(item).to_domain()
            for item in self._decoded_array(outcome.output.stdout)
        )

        return tuple(pull for pull in pulls if pull.branch in branches)

    def _listed(self, *, repo: str, branch: str, state: str) -> int | None:
        argv = ["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", state, "--json", "number"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        items = self._decoded_array(outcome.output.stdout)
        if not items:
            return None

        return GhPullRequestPayload.from_dict(items[0]).number

    def create_pull_request(self, *, repo: str, branch: str, base: str, title: str, body: str) -> int:
        argv = [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--assignee",
            "@me",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body-file",
            "-",
        ]
        outcome = self._call.run(argv, stdin=body, safe_to_repeat=False)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return self._number_of(outcome.output.stdout)

    def pull_request_state(self, *, repo: str, number: int) -> PullRequestStatus:
        argv = ["gh", "pr", "view", str(number), "--repo", repo, "--json", "state,mergeable"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return GhPullRequestStatePayload.from_dict(self._decoded_object(outcome.output.stdout)).to_domain()

    def reviews(self, *, repo: str, pull_request: int) -> tuple[PullRequestReview, ...]:
        reviews = tuple(
            GhPullRequestReviewPayload.from_dict(item)
            for item in self._decoded_array(self._gh_api(f"repos/{repo}/pulls/{pull_request}/reviews"))
        )
        comments = tuple(
            GhPullRequestReviewCommentPayload.from_dict(item)
            for item in self._decoded_array(self._gh_api(f"repos/{repo}/pulls/{pull_request}/comments"))
        )
        by_review: dict[int, list[PullRequestReviewComment]] = defaultdict(list)
        for comment in comments:
            by_review[comment.pull_request_review_id].append(comment.to_domain())

        return tuple(review.to_domain(comments=tuple(by_review[review.id])) for review in reviews)

    def _gh_api(self, resource: str) -> str:
        outcome = self._call.run(["gh", "api", resource], stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"gh api {resource}: {outcome.reason}")

        return outcome.output.stdout

    def authenticated_as(self) -> str | None:
        outcome = self._call.run(["gh", "api", "user", "--jq", ".login"], stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            return None

        return outcome.output.stdout.strip() or None

    def can_read(self, *, repo: str) -> bool:
        outcome = self._call.run(["gh", "repo", "view", repo, "--json", "name"], stdin="", safe_to_repeat=True)

        return outcome.output.code == 0

    @staticmethod
    def _number_of(stdout: str) -> int:
        url = stdout.strip()
        try:
            return int(url.rsplit("/", maxsplit=1)[-1])
        except ValueError as error:
            raise UnreadableForumError(f"gh did not print the url of the pull request it created: {url!r}") from error

    @classmethod
    def _decoded_array(cls, stdout: str) -> list[dict[str, object]]:
        data = cls._decoded(stdout)
        if not isinstance(data, list):
            raise UnreadableForumError(f"gh has to return an array, not {type(data).__name__}")

        return data

    @classmethod
    def _decoded_object(cls, stdout: str) -> dict[str, object]:
        data = cls._decoded(stdout)
        if not isinstance(data, dict):
            raise UnreadableForumError(f"gh has to return an object, not {type(data).__name__}")

        return data

    @staticmethod
    def _decoded(stdout: str) -> object:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise UnreadableForumError(f"gh did not return JSON: {error}") from error
