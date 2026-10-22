from __future__ import annotations

import json

import pytest

from slice_runner.domain.branch_pull_request import BranchPullRequest
from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.pull_request_mergeability import PullRequestMergeability
from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment
from slice_runner.domain.pull_request_review_state import PullRequestReviewState
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.infrastructure.gh_forum import GhForum
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother

_REPO = "alcaptar/slice-runner"
_BRANCH = "slice/05-prechecks-deterministas"
_OTHER_BRANCH = "slice/06-pausa-de-alineacion"
_BASE = "master"
_TITLE = "feat(entrega-de-la-slice): commitear solo lo juzgado y abrir la pull request"
_BODY = "## Intencion\nsin esto el programa verifica y no entrega\n\nCloses #46\n"


class TestGhForum:
    def test_it_asks_gh_for_exactly_the_open_pull_requests_of_this_branch(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "list"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--state") == "open"
        assert argv.value_of("--json") == "number"

    def test_no_open_pull_request_reads_as_none_not_as_zero(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH) is None

    def test_a_recorded_open_pull_request_gives_back_its_number(self) -> None:
        recorded = GhResponseMother.pull_request_of_branch()
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH) == 47

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH)

    def test_a_response_that_is_not_json_is_rejected_instead_of_crashing_on_a_decode_error(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="not json at all", stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH)

    def test_a_response_that_is_not_an_array_is_rejected_too(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"number": 47}), stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH)


class TestGhForumLookingForThePullRequestOfAResumedRun:
    def test_it_asks_gh_for_the_pull_requests_of_this_branch_in_every_state(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        GhForum(call=GhCallDoubles.wired(process)).any_pull_request(repo=_REPO, branch=_BRANCH)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "list"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--state") == "all"
        assert argv.value_of("--json") == "number"

    def test_a_pull_request_already_merged_is_found_because_a_resumed_run_still_has_to_name_it(self) -> None:
        recorded = GhResponseMother.pull_request_of_branch()
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).any_pull_request(repo=_REPO, branch=_BRANCH) == 47

    def test_a_branch_that_never_had_a_pull_request_reads_as_none_not_as_zero(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).any_pull_request(repo=_REPO, branch=_BRANCH) is None

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(call=GhCallDoubles.wired(process)).any_pull_request(repo=_REPO, branch=_BRANCH)


class TestGhForumListingThePullRequestsOfSeveralBranchesAtOnce:
    def test_it_asks_gh_for_every_open_pull_request_of_the_repo_in_a_single_call(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(repo=_REPO, branches=(_BRANCH,))

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "list"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--state") == "open"
        assert argv.value_of("--json") == "number,headRefName"
        assert not argv.contains("--head")
        assert len(process.calls) == 1

    def test_only_the_branches_asked_for_come_back_matched_to_their_pull_request(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(
                code=0,
                stdout=json.dumps(
                    [{"number": 47, "headRefName": _BRANCH}, {"number": 48, "headRefName": "slice/09-otra"}]
                ),
                stderr="",
            )
        )

        result = GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(
            repo=_REPO, branches=(_BRANCH, _OTHER_BRANCH)
        )

        assert result == (BranchPullRequest(branch=_BRANCH, number=47),)

    def test_a_branch_with_no_open_pull_request_is_simply_absent_instead_of_carrying_a_none(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="[]", stderr=""))

        result = GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(repo=_REPO, branches=(_BRANCH,))

        assert result == ()

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(repo=_REPO, branches=(_BRANCH,))

    def test_a_response_that_is_not_json_is_rejected_instead_of_crashing_on_a_decode_error(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="not json at all", stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(repo=_REPO, branches=(_BRANCH,))

    def test_a_response_that_is_not_an_array_is_rejected_too(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"number": 47}), stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).open_pull_requests(repo=_REPO, branches=(_BRANCH,))


class TestGhForumOpeningTheSlicePullRequest:
    @staticmethod
    def _created(*, url: str = "https://github.com/alcaptar/slice-runner/pull/48") -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=0, stdout=f"{url}\n", stderr=""))

    def _create(self, process: ScriptedProcess) -> int:
        return GhForum(call=GhCallDoubles.wired(process)).create_pull_request(
            repo=_REPO, branch=_BRANCH, base=_BASE, title=_TITLE, body=_BODY
        )

    def test_it_asks_gh_for_a_pull_request_of_this_branch_against_this_base(self) -> None:
        process = self._created()

        self._create(process)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "pr", "create"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--base") == _BASE
        assert argv.value_of("--head") == _BRANCH
        assert argv.value_of("--title") == _TITLE

    def test_it_is_born_ready_for_review_because_a_draft_is_a_pull_request_nobody_is_asked_to_merge(self) -> None:
        process = self._created()

        self._create(process)

        assert not Argv(process.calls[0].argv).contains("--draft")

    def test_it_is_assigned_to_whoever_gh_is_authenticated_as_so_it_lands_in_their_own_list(self) -> None:
        process = self._created()

        self._create(process)

        assert Argv(process.calls[0].argv).value_of("--assignee") == "@me"

    def test_the_body_travels_by_stdin_so_no_shell_has_to_survive_its_markdown(self) -> None:
        process = self._created()

        self._create(process)

        assert Argv(process.calls[0].argv).value_of("--body-file") == "-"
        assert process.calls[0].stdin == _BODY

    def test_the_number_of_the_pull_request_is_read_from_the_url_gh_printed(self) -> None:
        assert self._create(self._created()) == 48

    def test_a_stdout_that_is_not_a_pull_request_url_is_rejected_instead_of_read_as_a_number(self) -> None:
        with pytest.raises(UnreadableForumError, match="not-a-url"):
            self._create(self._created(url="not-a-url"))

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="a pull request already exists"))

        with pytest.raises(GhCommandFailedError, match="already exists"):
            self._create(process)


class TestGhForumAskingWhatStateThePullRequestIsIn:
    @staticmethod
    def _answering(state: str, *, mergeable: str = "MERGEABLE") -> ScriptedProcess:
        return ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps({"state": state, "mergeable": mergeable}), stderr="")
        )

    def test_it_asks_gh_for_the_state_and_the_mergeability_of_exactly_this_pull_request(self) -> None:
        process = self._answering("MERGED")

        GhForum(call=GhCallDoubles.wired(process)).pull_request_state(repo=_REPO, number=60)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "pr", "view", "60"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--json") == "state,mergeable"

    def test_a_merged_pull_request_reads_as_merged(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("MERGED"))).pull_request_state(repo=_REPO, number=60)

        assert status.state is PullRequestState.MERGED

    def test_a_pull_request_closed_without_merging_is_told_apart_from_one_still_open(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("CLOSED"))).pull_request_state(repo=_REPO, number=60)

        assert status.state is PullRequestState.CLOSED

    def test_a_pull_request_still_open_reads_as_open(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("OPEN"))).pull_request_state(repo=_REPO, number=60)

        assert status.state is PullRequestState.OPEN

    def test_a_state_that_is_not_one_of_the_three_gh_returns_is_rejected_instead_of_read_as_unmerged(self) -> None:
        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(self._answering("DRAFT"))).pull_request_state(repo=_REPO, number=60)

    def test_a_mergeable_pull_request_reads_as_mergeable(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("OPEN", mergeable="MERGEABLE"))).pull_request_state(
            repo=_REPO, number=60
        )

        assert status.mergeability is PullRequestMergeability.MERGEABLE

    def test_a_pull_request_in_conflict_with_its_base_reads_as_conflicting(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("OPEN", mergeable="CONFLICTING"))).pull_request_state(
            repo=_REPO, number=60
        )

        assert status.mergeability is PullRequestMergeability.CONFLICTING

    def test_a_mergeability_gh_has_not_computed_yet_reads_as_unknown(self) -> None:
        status = GhForum(call=GhCallDoubles.wired(self._answering("OPEN", mergeable="UNKNOWN"))).pull_request_state(
            repo=_REPO, number=60
        )

        assert status.mergeability is PullRequestMergeability.UNKNOWN

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="no pull requests found for branch"))

        with pytest.raises(GhCommandFailedError, match="no pull requests found"):
            GhForum(call=GhCallDoubles.wired(process)).pull_request_state(repo=_REPO, number=60)

    def test_a_response_with_a_key_we_did_not_ask_for_is_rejected_instead_of_read_around(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(
                code=0,
                stdout=json.dumps({"state": "MERGED", "mergeable": "MERGEABLE", "mergedAt": "2026-08-05"}),
                stderr="",
            )
        )

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).pull_request_state(repo=_REPO, number=60)

    def test_a_response_that_is_not_an_object_is_rejected_instead_of_crashing_on_an_attribute(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps([{"state": "MERGED"}]), stderr=""))

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).pull_request_state(repo=_REPO, number=60)


class TestGhForumAskingWhoIsAuthenticated:
    def test_it_asks_gh_for_the_login_of_the_authenticated_user(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="someone\n", stderr=""))

        GhForum(call=GhCallDoubles.wired(process)).authenticated_as()

        assert process.calls[0].argv == ["gh", "api", "user", "--jq", ".login"]

    def test_the_login_printed_is_returned_stripped_of_its_trailing_newline(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="someone\n", stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).authenticated_as() == "someone"

    def test_no_authentication_reads_as_none_instead_of_raising(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="gh: To authenticate, run `gh auth login`"))

        assert GhForum(call=GhCallDoubles.wired(process)).authenticated_as() is None


class TestGhForumCheckingWhetherARepoCanBeRead:
    def test_it_asks_gh_to_view_exactly_this_repo(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"name": "slice-runner"}), stderr=""))

        GhForum(call=GhCallDoubles.wired(process)).can_read(repo=_REPO)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "repo", "view"]
        assert _REPO in process.calls[0].argv
        assert argv.value_of("--json") == "name"

    def test_a_repo_gh_can_view_reads_as_true(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"name": "slice-runner"}), stderr=""))

        assert GhForum(call=GhCallDoubles.wired(process)).can_read(repo=_REPO) is True

    def test_a_repo_gh_cannot_view_reads_as_false_instead_of_raising(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        assert GhForum(call=GhCallDoubles.wired(process)).can_read(repo=_REPO) is False


class TestGhForumRetryingTransientFailures:
    def test_a_transient_failure_listing_pull_requests_is_retried_until_it_succeeds(self) -> None:
        recorded = GhResponseMother.pull_request_of_branch()
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="connection reset by peer"),
            ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""),
        )

        assert GhForum(call=GhCallDoubles.wired(process)).open_pull_request(repo=_REPO, branch=_BRANCH) == 47
        assert len(process.calls) == 2

    def test_opening_a_pull_request_that_fails_transiently_is_never_retried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="connection reset by peer"))

        with pytest.raises(GhCommandFailedError):
            GhForum(call=GhCallDoubles.wired(process)).create_pull_request(
                repo=_REPO, branch=_BRANCH, base=_BASE, title=_TITLE, body=_BODY
            )

        assert len(process.calls) == 1


class TestGhForumReadingTheReviewsOfAPullRequest:
    @staticmethod
    def _answering(reviews: list[dict[str, object]], comments: list[dict[str, object]]) -> ScriptedProcess:
        return ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps(reviews), stderr=""),
            ProcessOutput(code=0, stdout=json.dumps(comments), stderr=""),
        )

    def test_it_asks_gh_for_the_reviews_and_the_inline_comments_of_exactly_this_pull_request(self) -> None:
        process = self._answering([], [])

        GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert process.calls[0].argv == ["gh", "api", f"repos/{_REPO}/pulls/60/reviews"]
        assert process.calls[1].argv == ["gh", "api", f"repos/{_REPO}/pulls/60/comments"]

    def test_a_review_comes_back_with_its_id_its_state_and_its_body(self) -> None:
        process = self._answering(
            [{"id": 101, "state": "CHANGES_REQUESTED", "body": "arregla el manejo de errores"}], []
        )

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert len(reviews) == 1
        assert (reviews[0].id, reviews[0].state, reviews[0].body) == (
            101,
            PullRequestReviewState.CHANGES_REQUESTED,
            "arregla el manejo de errores",
        )

    def test_a_review_with_no_inline_comments_comes_back_with_none_instead_of_crashing(self) -> None:
        process = self._answering([{"id": 101, "state": "APPROVED", "body": "se ve bien"}], [])

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert reviews[0].comments == ()

    def test_every_review_state_gh_can_send_is_read_without_being_rejected(self) -> None:
        process = self._answering(
            [
                {"id": 1, "state": "APPROVED", "body": ""},
                {"id": 2, "state": "CHANGES_REQUESTED", "body": ""},
                {"id": 3, "state": "COMMENTED", "body": ""},
                {"id": 4, "state": "DISMISSED", "body": ""},
                {"id": 5, "state": "PENDING", "body": ""},
            ],
            [],
        )

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert [review.state for review in reviews] == list(PullRequestReviewState)

    def test_an_inline_comment_is_matched_to_its_review_by_the_review_id_gh_reported(self) -> None:
        process = self._answering(
            [
                {"id": 101, "state": "CHANGES_REQUESTED", "body": ""},
                {"id": 102, "state": "CHANGES_REQUESTED", "body": ""},
            ],
            [
                {
                    "body": "esto rompe si la lista viene vacia",
                    "path": "src/a.py",
                    "line": 10,
                    "pull_request_review_id": 101,
                },
                {"body": "aqui falta un test", "path": "src/b.py", "line": 3, "pull_request_review_id": 102},
                {
                    "body": "y aqui otro mas sobre lo mismo",
                    "path": "src/a.py",
                    "line": 12,
                    "pull_request_review_id": 101,
                },
            ],
        )

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        by_id = {review.id: review.comments for review in reviews}
        assert by_id == {
            101: (
                PullRequestReviewComment(body="esto rompe si la lista viene vacia", path="src/a.py", line=10),
                PullRequestReviewComment(body="y aqui otro mas sobre lo mismo", path="src/a.py", line=12),
            ),
            102: (PullRequestReviewComment(body="aqui falta un test", path="src/b.py", line=3),),
        }

    def test_an_inline_comment_carries_its_file_and_its_line(self) -> None:
        process = self._answering(
            [{"id": 101, "state": "CHANGES_REQUESTED", "body": ""}],
            [
                {
                    "body": PullRequestReviewCommentMother.ANCHORED_BODY,
                    "path": PullRequestReviewCommentMother.PATH,
                    "line": PullRequestReviewCommentMother.LINE,
                    "pull_request_review_id": 101,
                }
            ],
        )

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert reviews[0].comments == (PullRequestReviewCommentMother.anchored_to_a_line(),)

    def test_a_comment_that_went_stale_after_a_push_arrives_with_its_file_and_without_a_line(self) -> None:
        process = self._answering(
            [{"id": 101, "state": "CHANGES_REQUESTED", "body": ""}],
            [
                {
                    "body": PullRequestReviewCommentMother.STALE_BODY,
                    "path": PullRequestReviewCommentMother.PATH,
                    "line": None,
                    "pull_request_review_id": 101,
                }
            ],
        )

        reviews = GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

        assert reviews[0].comments == (PullRequestReviewCommentMother.without_a_line_because_it_went_stale(),)

    def test_a_non_zero_exit_listing_reviews_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"))

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

    def test_a_non_zero_exit_listing_comments_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="[]", stderr=""),
            ProcessOutput(code=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"),
        )

        with pytest.raises(GhCommandFailedError, match="Could not resolve"):
            GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)

    def test_a_review_that_is_not_one_of_the_five_states_gh_returns_is_rejected(self) -> None:
        process = self._answering([{"id": 101, "state": "DRAFT", "body": ""}], [])

        with pytest.raises(UnreadableForumError):
            GhForum(call=GhCallDoubles.wired(process)).reviews(repo=_REPO, pull_request=60)
