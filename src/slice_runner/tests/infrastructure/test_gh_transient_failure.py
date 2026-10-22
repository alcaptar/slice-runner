from __future__ import annotations

from slice_runner.infrastructure.gh_transient_failure import GhTransientFailure


class TestGhTransientFailure:
    def test_a_connection_reset_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of('Post "https://api.github.com/graphql": read: connection reset by peer')

    def test_a_secondary_rate_limit_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of(
            "HTTP 403: You have exceeded a secondary rate limit and have been temporarily blocked"
        )

    def test_a_bad_gateway_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("HTTP 502: Bad Gateway")

    def test_matching_ignores_case(self) -> None:
        assert GhTransientFailure.of("Connection Reset by peer")

    def test_a_missing_issue_is_not_read_as_transient(self) -> None:
        assert not GhTransientFailure.of("GraphQL: Could not resolve to an Issue with the number of 999999.")

    def test_a_missing_permission_is_not_read_as_transient(self) -> None:
        assert not GhTransientFailure.of("HTTP 403: Resource not accessible by integration")

    def test_a_shorthand_rate_limited_fixture_is_not_mistaken_for_the_real_message(self) -> None:
        assert not GhTransientFailure.of("rate limited")

    def test_the_real_outage_json_parsing_failure_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("unexpected end of JSON input")

    def test_the_real_outage_no_server_available_message_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("No server is currently available to service your request")

    def test_a_502_worded_differently_from_the_known_marker_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("HTTP 502: The upstream service could not be reached right now")

    def test_a_504_worded_differently_from_the_known_marker_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("HTTP 504: The request took too long to complete upstream")

    def test_a_generic_4xx_is_not_read_as_transient_through_the_status_code_path(self) -> None:
        assert not GhTransientFailure.of("HTTP 422: Validation Failed")

    def test_an_invalid_argument_error_is_not_read_as_transient(self) -> None:
        assert not GhTransientFailure.of("unknown flag: --foo")

    def test_a_connection_failure_without_a_status_code_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of(
            "gh pr view 337 --repo alcaptar/slice-runner --json state,mergeable: error connecting to api.github.com\n"
            "check your internet connection or https://githubstatus.com"
        )

    def test_a_connection_failure_against_any_github_host_is_read_as_transient(self) -> None:
        assert GhTransientFailure.of("gh: error connecting to uploads.github.com")
