from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import UnreadableIssueError
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.infrastructure.gh_child_issues import GhChildIssues
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother

_REPO = "alcaptar/slice-runner"


class TestReadingTheSubissuesThroughTheGraphInterface:
    @staticmethod
    def _adapter(process: ScriptedProcess) -> GhChildIssues:
        return GhChildIssues(call=GhCallDoubles.wired(process))

    @staticmethod
    def _answering(payload: object) -> ScriptedProcess:
        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_it_lists_the_subissues_with_the_paginated_interface_and_not_with_the_search(self) -> None:
        process = self._answering([])

        self._adapter(process).of_parent(repo=_REPO, parent=512)

        assert [call.argv for call in process.calls] == [
            ["gh", "api", "--paginate", "repos/alcaptar/slice-runner/issues/512/sub_issues"]
        ]

    def test_a_recorded_response_with_a_label_without_description_projects_number_title_and_state(self) -> None:
        process = self._answering(GhResponseMother.sub_issues_of_parent())

        children = self._adapter(process).of_parent(repo=_REPO, parent=512)

        assert [(child.number, child.slice_id, child.state) for child in children] == [
            (513, SliceIdentity(ordinal=1, name="claude-a-la-izquierda"), IssueState.CLOSED),
            (516, SliceIdentity(ordinal=4, name="reabrir-un-workspace"), IssueState.OPEN),
        ]

    def test_the_canonical_id_comes_from_a_title_with_a_user_story(self) -> None:
        entry = {"number": 7, "title": "HU-123 slice-01 (x): y", "state": "open"}

        children = self._adapter(self._answering([entry])).of_parent(repo=_REPO, parent=512)

        assert children[0].slice_id.canonical == "HU-123-01"

    def test_an_entry_missing_a_key_the_projection_consumes_is_rejected(self) -> None:
        entry = {"title": "slice-01 (x): y", "state": "open"}

        with pytest.raises(UnreadableIssueError):
            self._adapter(self._answering([entry])).of_parent(repo=_REPO, parent=512)

    def test_a_state_outside_open_and_closed_is_rejected(self) -> None:
        entry = {"number": 7, "title": "slice-01 (x): y", "state": "merged"}

        with pytest.raises(UnreadableIssueError):
            self._adapter(self._answering([entry])).of_parent(repo=_REPO, parent=512)

    def test_a_title_that_does_not_open_with_the_slice_heading_is_rejected(self) -> None:
        entry = {"number": 7, "title": "a plain issue", "state": "open"}

        with pytest.raises(UnreadableIssueError):
            self._adapter(self._answering([entry])).of_parent(repo=_REPO, parent=512)

    def test_a_response_that_is_not_an_array_is_rejected(self) -> None:
        with pytest.raises(UnreadableIssueError):
            self._adapter(self._answering({"message": "Not Found"})).of_parent(repo=_REPO, parent=512)

    def test_a_failing_command_raises_with_the_reason_instead_of_returning_an_empty_list(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="gh: Not Found (HTTP 404)"))

        with pytest.raises(GhCommandFailedError, match="Not Found"):
            self._adapter(process).of_parent(repo=_REPO, parent=512)
