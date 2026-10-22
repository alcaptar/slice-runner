from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.control_command import ControlCommand
from slice_runner.domain.controls import Controls
from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.exceptions import (
    EmptyIssueBodyError,
    LaggingSearchIndexError,
    MalformedConventionLineError,
    UnreadableFindingsError,
    UnreadableIssueError,
    UnreadableRunError,
)
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.order import Order
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.domain.run import Run
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.domain.source import Source, SourceKind
from slice_runner.domain.step import Step
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.catch_up_conflict_comment import CatchUpConflictComment
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError, GhRunRepository
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.infrastructure.reset_comment import ResetComment
from slice_runner.infrastructure.veto_findings_comment import VetoFindingsComment
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.findings_history_mother import FindingsHistoryMother
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

_REPO = "alcaptar/slice-runner"
_OTHER_REPO = "alcaptar/otro-repo"

_SUB2_BODY = (
    "REPO: alcaptar/otro-repo\n"
    "INTENCION: comprobar que el orden sale del titulo y no de la interfaz de programacion\n"
    "ACEPTACION: se ordena por slice-NN aunque la api la devuelva antes\n"
    "SENAL: exenta - spike de medicion\n"
)

_SUB1_BODY = (
    "INTENCION: hoy no hay forma de medir el formato nuevo sin crearlo\n"
    "ACEPTACION: el cuerpo se lee entero; los criterios llegan como lineas\n"
    "ACEPTACION: el bloque de estado se puede reescribir sin tocar lo de arriba\n"
    "SENAL: exenta - spike de medicion\n"
    "\n"
    "<!-- slice-runner:estado\n"
    '{"step": "await-ci", "retry_instruction": "", '
    '"tree_unexpected": false, '
    '"previous_call_died": false, "catching_up_the_branch": false, "control_retries": 1, '
    '"hygiene_retries": 0, "verify_retries": 0, '
    '"ci_retries": 0, "catch_up_retries": 0, "indeterminate_ticks": 2, '
    '"verify_discards": 0, '
    '"implement_discards": 0, "control_rounds_logged": 0, "verify_rounds_logged": 0, '
    '"last_reviewed_id": 0, "requested_changes": []}\n'
    "-->\n\n"
)


class TestReadingTheParent:
    @staticmethod
    def _process() -> ScriptedProcess:
        recorded = GhResponseMother.parent_with_two_children()

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""))

    def test_it_asks_gh_for_exactly_the_fields_it_reads(self) -> None:
        process = self._process()

        GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "issue", "view", "43"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--json") == "body,subIssuesSummary,state"

    def test_every_line_under_the_decisions_heading_arrives_in_order_without_its_leading_dash(self) -> None:
        body = "## Intencion\nx\n\n## Decisiones\n- la primera decision\n- la segunda decision\n\n## Controles\n"

        parent = GhRunRepository(call=GhCallDoubles.wired(self._process_with_body(body))).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.decisions == ("la primera decision", "la segunda decision")

    def test_a_parent_without_the_decisions_section_reads_as_no_decisions(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.decisions == ()

    def test_the_decisions_of_a_parent_do_not_depend_on_which_repo_the_slice_belongs_to(self) -> None:
        body = "## Decisiones\n- una decision de la feature\n"

        parent = GhRunRepository(call=GhCallDoubles.wired(self._process_with_body(body))).read_parent(
            repo=_REPO, issue=43, slice_repo=_OTHER_REPO
        )

        assert parent.decisions == ("una decision de la feature",)

    def test_the_state_of_the_issue_becomes_the_state_of_the_parent(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.state is IssueState.OPEN

    def test_the_intention_is_the_text_of_its_own_section(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.intention == "Spike de medicion del formato de subissues. Este issue se borra al terminar."

    def test_sources_with_no_repo_line_belong_to_the_issue_own_repo(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.sources == (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)

    def test_sources_under_a_repo_subsection_only_surface_when_that_repo_is_asked_for(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=_OTHER_REPO
        )

        assert parent.sources == (Source(kind=SourceKind.DOC, path="templates/CLAUDE.md"),)

    def test_controls_are_filtered_by_repo_the_same_way_sources_are(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.controls == Controls(
            commands=(
                ControlCommand(name="lint", command="make linting"),
                ControlCommand(name="tests", command="make test"),
            ),
            exemption_reason=None,
        )

    def test_the_exemption_line_is_read_as_a_declared_exemption_and_never_as_a_command_to_run(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=_OTHER_REPO
        )

        assert parent.controls == Controls(
            commands=(), exemption_reason="la integracion continua solo publica en master"
        )

    def test_the_subissue_count_is_the_graphs_witness_not_something_counted_here(self) -> None:
        parent = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_parent(
            repo=_REPO, issue=43, slice_repo=None
        )

        assert parent.subissue_count == 2

    @staticmethod
    def _process_with_body(body: str) -> ScriptedProcess:
        payload = {
            "body": body,
            "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1},
            "state": "OPEN",
        }

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_a_dash_line_under_sources_that_does_not_match_the_source_format_is_rejected_not_dropped(self) -> None:
        body = "## Fuentes de convencion\n- CLAUDE.md\n"
        process = self._process_with_body(body)

        with pytest.raises(MalformedConventionLineError, match=re.escape("- CLAUDE.md")):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

    def test_a_dash_line_under_controls_that_does_not_match_the_control_format_is_rejected_not_dropped(self) -> None:
        body = "## Controles\n- lint make linting\n"
        process = self._process_with_body(body)

        with pytest.raises(MalformedConventionLineError, match=re.escape("- lint make linting")):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

    def test_a_blank_line_under_sources_does_not_raise(self) -> None:
        body = "## Fuentes de convencion\n- doc: CLAUDE.md\n\n\n## Controles\n- lint: make linting\n"
        process = self._process_with_body(body)

        parent = GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.sources == (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)

    def test_a_repo_subsection_heading_under_controls_does_not_raise(self) -> None:
        body = (
            "## Fuentes de convencion\n- doc: CLAUDE.md\n"
            "## Controles\n- lint: make linting\n\n### alcaptar/otro-repo\n- ninguno: solo publica en master\n"
        )
        process = self._process_with_body(body)

        parent = GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(
            repo=_REPO, issue=43, slice_repo=_OTHER_REPO
        )

        assert parent.controls == Controls(commands=(), exemption_reason="solo publica en master")

    def test_a_repo_with_no_controls_of_its_own_reads_as_undeclared_and_not_as_exempt(self) -> None:
        body = "## Fuentes de convencion\n- doc: CLAUDE.md\n## Controles\n- lint: make linting\n"
        process = self._process_with_body(body)

        parent = GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(
            repo=_REPO, issue=43, slice_repo=_OTHER_REPO
        )

        assert parent.controls == Controls(commands=(), exemption_reason=None)

    def test_a_repo_that_declares_the_exemption_next_to_real_controls_is_rejected_instead_of_running_one_of_them(
        self,
    ) -> None:
        body = "## Controles\n- ninguno: solo publica en master\n- lint: make linting\n"
        process = self._process_with_body(body)

        with pytest.raises(MalformedConventionLineError, match="ninguno"):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)


class TestReadingTheChildren:
    @staticmethod
    def _process(*, children: list[dict[str, object]] | None = None) -> ScriptedProcess:
        payload = children if children is not None else GhResponseMother.children_of_parent()

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_it_searches_for_this_exact_parent_issue_and_asks_for_only_the_fields_it_reads(self) -> None:
        process = self._process()

        GhRunRepository(call=GhCallDoubles.wired(process)).read_children(repo=_REPO, parent=43, expected=2)

        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:3] == ["gh", "issue", "list"]
        assert argv.value_of("--search") == f"parent-issue:{_REPO}#43"
        assert argv.value_of("--state") == "all"
        assert argv.value_of("--json") == "number,title,body,labels,state"

    def test_ordering_is_by_the_slice_number_in_the_title_not_by_the_order_the_search_returned(self) -> None:
        out_of_order = [
            {
                "number": 1,
                "title": "slice-02 (b): later slice, first in the response",
                "body": "",
                "labels": [],
                "state": "OPEN",
            },
            {
                "number": 2,
                "title": "slice-01 (a): earlier slice, last in the response",
                "body": "",
                "labels": [],
                "state": "OPEN",
            },
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=out_of_order))).read_children(
            repo=_REPO, parent=43, expected=2
        )

        assert [child.slice_id.canonical for child in children] == ["slice-01", "slice-02"]

    def test_the_repo_line_of_the_body_becomes_the_subissue_repo(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].repo is None
        assert by_slice["slice-02"].repo == _OTHER_REPO

    def test_every_acceptance_line_of_the_body_arrives_as_its_own_criterion_in_the_order_it_was_written(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].criteria == (
            "el cuerpo se lee entero; los criterios llegan como lineas",
            "el bloque de estado se puede reescribir sin tocar lo de arriba",
        )

    def test_every_decision_line_of_the_body_arrives_in_order_without_its_prefix(self) -> None:
        body = "INTENCION: x\nDECISION: la primera decision\nACEPTACION: y\nDECISION: la segunda decision\n"
        entry = {**GhResponseMother.children_of_parent()[0], "body": body}

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=[entry]))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].decisions == ("la primera decision", "la segunda decision")

    def test_a_body_without_any_decision_line_reads_as_no_decisions(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        assert all(child.decisions == () for child in children)

    def test_the_intention_and_the_signal_of_the_slice_arrive_as_the_lines_that_declare_them(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].intention == "hoy no hay forma de medir el formato nuevo sin crearlo"
        assert by_slice["slice-01"].signal == "exenta - spike de medicion"

    def test_the_excludes_line_of_the_body_becomes_the_subissue_excludes(self) -> None:
        with_excludes = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": "INTENCION: z\nEXCLUYE: el panel de grafana que consume esta serie\n",
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_excludes))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].excludes == "el panel de grafana que consume esta serie"

    def test_a_body_without_excludes_reads_it_as_empty_because_that_is_the_shape_of_an_already_created_subissue(
        self,
    ) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].excludes == ""
        assert by_slice["slice-01"].signal == "exenta - spike de medicion"

    def test_the_replaces_line_of_the_body_becomes_the_subissue_replaces(self) -> None:
        with_replaces = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": "INTENCION: z\nSUSTITUYE: si - el adaptador viejo; apagando el flag\n",
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_replaces))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].replaces == "si - el adaptador viejo; apagando el flag"

    def test_a_body_without_replaces_reads_it_as_empty_because_that_is_the_shape_of_an_already_created_subissue(
        self,
    ) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].replaces == ""

    def test_a_body_that_declares_none_of_them_reads_as_empty_instead_of_refusing_to_be_read(self) -> None:
        bodiless = [{"number": 1, "title": "slice-01 (a): no prose at all", "body": "", "labels": [], "state": "OPEN"}]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=bodiless))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert (
            children[0].intention,
            children[0].criteria,
            children[0].signal,
            children[0].excludes,
            children[0].replaces,
        ) == (
            "",
            (),
            "",
            "",
            "",
        )

    def test_a_body_with_no_state_block_reads_as_no_run_yet(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-02"].run is None

    def test_a_body_with_a_state_block_reads_the_run_it_holds(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].run == RunMother.awaiting_ci()

    def test_a_state_block_with_a_discarded_call_reads_it_back_so_the_invocation_that_closes_can_write_it(self) -> None:
        with_discard = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "await-merge", "discarded_call": '
                    '{"step": "verify", "cause": "failed-call", "reason": "claude: command not found"}}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_discard))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.awaiting_merge_after_discarding(DiscardedCallMother.of_a_failed_call())

    def test_a_state_block_with_a_spend_reads_it_back_so_a_reinvocation_sees_the_prior_cost(self) -> None:
        with_spend = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "verify", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
                    '"indeterminate_ticks": 0, "verify_discards": 0, '
                    '"spend": {"cost_usd": 0.3433209, "turns": 9, "duration_ms": 36315, "calls": 1, '
                    '"models": ["claude-sonnet-5"], "input_tokens": 13, "output_tokens": 1159, '
                    '"cache_creation_tokens": 42251, "cache_read_tokens": 241303, "ttft_ms": 5588, '
                    '"duration_api_ms": 32189}}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_spend))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.judging_after_spending(HarnessSpendMother.of_the_implementer_call())

    def test_a_state_block_with_a_spend_before_reopening_key_written_before_this_slice_is_read_ignoring_it(
        self,
    ) -> None:
        with_the_legacy_key = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "verify", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
                    '"indeterminate_ticks": 0, "verify_discards": 0, '
                    '"spend_before_reopening": {"cost_usd": 0.3433209, "turns": 9, "duration_ms": 36315, '
                    '"calls": 1, "models": ["claude-sonnet-5"], "input_tokens": 13, "output_tokens": 1159, '
                    '"cache_creation_tokens": 42251, "cache_read_tokens": 241303, "ttft_ms": 5588, '
                    '"duration_api_ms": 32189}}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_the_legacy_key))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.judging()

    def test_a_state_block_written_before_this_slice_with_no_catch_up_retries_key_reads_it_as_never_caught_up(
        self,
    ) -> None:
        without_the_key = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "await-ci", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
                    '"indeterminate_ticks": 0, "verify_discards": 0}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=without_the_key))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.about_to_ask_the_ci()

    def test_a_state_block_written_before_this_slice_with_no_verify_rounds_logged_key_reads_it_as_zero(self) -> None:
        without_the_key = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "verify", "control_retries": 0, "verify_retries": 0, "ci_retries": 0, '
                    '"indeterminate_ticks": 0, "verify_discards": 0}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=without_the_key))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.judging()

    def test_a_state_block_with_a_requested_change_reads_back_its_anchored_comments_with_file_and_line(self) -> None:
        with_requested_changes = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    "INTENCION: z\n\n"
                    "<!-- slice-runner:estado\n"
                    '{"step": "implement", "last_reviewed_id": 101, '
                    '"requested_changes": [{"body": "", "comments": ['
                    '{"body": "esta linea sobra", "path": "src/slice_runner/domain/run.py", "line": 42}, '
                    '{"body": "esto ya no aplica", "path": "src/slice_runner/domain/run.py", "line": null}]}]}\n'
                    "-->\n"
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(
            call=GhCallDoubles.wired(self._process(children=with_requested_changes))
        ).read_children(repo=_REPO, parent=43, expected=1)

        assert children[0].run == Run(
            step=Step.IMPLEMENT,
            last_reviewed_id=101,
            requested_changes=(
                RequestedChange(
                    body="",
                    comments=(
                        PullRequestReviewCommentMother.anchored_to_a_line(),
                        PullRequestReviewCommentMother.without_a_line_because_it_went_stale(),
                    ),
                ),
            ),
        )

    def test_a_state_block_with_previous_call_died_reads_it_back_so_the_next_round_knows_the_call_died(self) -> None:
        with_a_dead_call = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": (
                    'INTENCION: z\n\n<!-- slice-runner:estado\n{"step": "implement", "previous_call_died": true}\n-->\n'
                ),
                "labels": [],
                "state": "OPEN",
            }
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=with_a_dead_call))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].run == RunMother.implementing_after_a_dead_call()

    def test_the_macro_state_label_present_on_the_issue_is_read_as_the_issue_label(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].label is IssueLabel.IN_PROGRESS
        assert by_slice["slice-02"].label is IssueLabel.PENDING

    def test_a_foreign_per_story_label_alongside_the_macro_label_does_not_change_which_state_read_children_resolves(
        self,
    ) -> None:
        macro = {"id": "2", "name": IssueLabel.PENDING.value, "description": "", "color": "000000"}
        foreign = {"id": "1", "name": "origen:HU-123", "description": "", "color": "000000"}

        for labels in ([foreign, macro], [macro, foreign]):
            child = [{"number": 1, "title": "slice-01 (name): resumen", "body": "", "labels": labels, "state": "OPEN"}]

            children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=child))).read_children(
                repo=_REPO, parent=43, expected=1
            )

            assert children[0].label is IssueLabel.PENDING, (
                f"a foreign `origen:` label placed {labels} confused which state label was resolved"
            )

    def test_the_gh_issue_state_becomes_the_subissue_state(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].state is IssueState.CLOSED
        assert by_slice["slice-02"].state is IssueState.OPEN

    def test_a_search_that_returns_fewer_subissues_than_the_graph_knows_about_raises_instead_of_deciding_short(
        self,
    ) -> None:
        with pytest.raises(LaggingSearchIndexError):
            GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(repo=_REPO, parent=43, expected=3)

    def test_a_subissue_title_with_no_slice_identifier_is_rejected_instead_of_sorted_arbitrarily(self) -> None:
        malformed = [{"number": 1, "title": "an issue with no slice id", "body": "", "labels": [], "state": "OPEN"}]

        with pytest.raises(UnreadableIssueError, match="slice-NN"):
            GhRunRepository(call=GhCallDoubles.wired(self._process(children=malformed))).read_children(
                repo=_REPO, parent=43, expected=1
            )

    def test_a_state_block_that_is_not_valid_json_is_rejected_as_unreadable(self) -> None:
        malformed = [
            {
                "number": 1,
                "title": "slice-01 (x): y",
                "body": "INTENCION: z\n\n<!-- slice-runner:estado\n{not json}\n-->\n",
                "labels": [],
                "state": "OPEN",
            }
        ]

        with pytest.raises(UnreadableRunError):
            GhRunRepository(call=GhCallDoubles.wired(self._process(children=malformed))).read_children(
                repo=_REPO, parent=43, expected=1
            )


class TestReadingASingleSubissue:
    @staticmethod
    def _process() -> ScriptedProcess:
        payload = GhResponseMother.children_of_parent()[1]

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_it_asks_gh_to_view_this_one_issue_and_only_the_fields_it_reads(self) -> None:
        process = self._process()

        GhRunRepository(call=GhCallDoubles.wired(process)).read_subissue(repo=_REPO, issue=49)

        assert process.calls[0].argv == [
            "gh",
            "issue",
            "view",
            "49",
            "--repo",
            _REPO,
            "--json",
            "number,title,body,labels,state",
        ]

    def test_the_subissue_it_returns_carries_the_same_fields_a_search_result_would(self) -> None:
        subissue = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_subissue(repo=_REPO, issue=49)

        assert subissue.slice_id.canonical == "slice-02"
        assert subissue.repo == _OTHER_REPO
        assert subissue.label is IssueLabel.PENDING
        assert subissue.state is IssueState.OPEN
        assert subissue.run is None

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 404: Not Found"))

        with pytest.raises(GhCommandFailedError, match="HTTP 404"):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_subissue(repo=_REPO, issue=49)


class TestWritingTheExecutionStateBlock:
    @staticmethod
    def _process(*, body: str, edit_code: int = 0) -> ScriptedProcess:
        return ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps({"body": body}), stderr=""),
            ProcessOutput(code=edit_code, stdout="", stderr=""),
        )

    def test_a_body_with_no_block_yet_gets_one_appended_after_the_prose(self) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO, issue=44, run=RunMother.implementing()
        )

        assert process.calls[1].stdin == (
            "REPO: alcaptar/otro-repo\n"
            "INTENCION: comprobar que el orden sale del titulo y no de la interfaz de programacion\n"
            "ACEPTACION: se ordena por slice-NN aunque la api la devuelva antes\n"
            "SENAL: exenta - spike de medicion\n"
            "\n"
            "<!-- slice-runner:estado\n"
            '{"step": "implement", "retry_instruction": "", '
            '"tree_unexpected": false, '
            '"previous_call_died": false, "catching_up_the_branch": false, '
            '"control_retries": 0, "hygiene_retries": 0, "verify_retries": 0, '
            '"ci_retries": 0, "catch_up_retries": 0, "indeterminate_ticks": 0, '
            '"verify_discards": 0, '
            '"implement_discards": 0, "control_rounds_logged": 0, "verify_rounds_logged": 0, '
            '"last_reviewed_id": 0, "requested_changes": []}\n'
            "-->\n"
        )

    def test_a_block_written_now_carries_neither_the_alignment_nor_the_correction_nor_the_understand_discards(
        self,
    ) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO, issue=44, run=RunMother.implementing()
        )

        block = re.search(r"<!-- slice-runner:estado\n(.*?)\n-->", process.calls[1].stdin, re.DOTALL)
        assert block is not None
        assert {"alignment", "corrected", "understand_discards"} & json.loads(block.group(1)).keys() == set()

    def test_a_run_carrying_a_dead_previous_call_writes_it_as_true_so_the_next_round_reads_it_back(self) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO, issue=44, run=RunMother.implementing_after_a_dead_call()
        )

        block = re.search(r"<!-- slice-runner:estado\n(.*?)\n-->", process.calls[1].stdin, re.DOTALL)
        assert block is not None
        assert json.loads(block.group(1))["previous_call_died"] is True

    def test_a_body_that_already_has_a_block_gets_only_the_block_replaced(self) -> None:
        process = self._process(body=_SUB1_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_REPO, issue=45, run=RunMother.awaiting_merge()
        )

        assert process.calls[1].stdin == (
            "INTENCION: hoy no hay forma de medir el formato nuevo sin crearlo\n"
            "ACEPTACION: el cuerpo se lee entero; los criterios llegan como lineas\n"
            "ACEPTACION: el bloque de estado se puede reescribir sin tocar lo de arriba\n"
            "SENAL: exenta - spike de medicion\n"
            "\n"
            "<!-- slice-runner:estado\n"
            '{"step": "await-merge", "retry_instruction": "", '
            '"tree_unexpected": false, '
            '"previous_call_died": false, "catching_up_the_branch": false, '
            '"control_retries": 0, "hygiene_retries": 0, "verify_retries": 0, '
            '"ci_retries": 0, "catch_up_retries": 0, "indeterminate_ticks": 0, '
            '"verify_discards": 0, '
            '"implement_discards": 0, "control_rounds_logged": 0, "verify_rounds_logged": 0, '
            '"last_reviewed_id": 0, "requested_changes": []}\n'
            "-->\n\n"
        )

    def test_a_run_with_a_requested_change_writes_its_anchored_comments_with_file_and_line(self) -> None:
        process = self._process(body=_SUB2_BODY)
        run = Run(
            step=Step.IMPLEMENT,
            last_reviewed_id=101,
            requested_changes=(
                RequestedChange(
                    body="",
                    comments=(
                        PullRequestReviewCommentMother.anchored_to_a_line(),
                        PullRequestReviewCommentMother.without_a_line_because_it_went_stale(),
                    ),
                ),
            ),
        )

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(repo=_OTHER_REPO, issue=44, run=run)

        block = re.search(r"<!-- slice-runner:estado\n(.*?)\n-->", process.calls[1].stdin, re.DOTALL)
        assert block is not None
        written = json.loads(block.group(1))
        assert written["requested_changes"] == [
            {
                "body": "",
                "comments": [
                    {"body": "esta linea sobra", "path": "src/slice_runner/domain/run.py", "line": 42},
                    {"body": "esto ya no aplica", "path": "src/slice_runner/domain/run.py"},
                ],
            }
        ]

    def test_a_run_with_a_measured_spend_writes_it_nested_under_its_own_key_so_reinvoking_keeps_the_budget(
        self,
    ) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO,
            issue=44,
            run=RunMother.judging_after_spending(HarnessSpendMother.of_the_implementer_call()),
        )

        assert process.calls[1].stdin == (
            "REPO: alcaptar/otro-repo\n"
            "INTENCION: comprobar que el orden sale del titulo y no de la interfaz de programacion\n"
            "ACEPTACION: se ordena por slice-NN aunque la api la devuelva antes\n"
            "SENAL: exenta - spike de medicion\n"
            "\n"
            "<!-- slice-runner:estado\n"
            '{"step": "verify", "retry_instruction": "", '
            '"tree_unexpected": false, '
            '"previous_call_died": false, "catching_up_the_branch": false, '
            '"control_retries": 0, "hygiene_retries": 0, "verify_retries": 0, '
            '"ci_retries": 0, "catch_up_retries": 0, "indeterminate_ticks": 0, '
            '"verify_discards": 0, '
            '"implement_discards": 0, "control_rounds_logged": 0, "verify_rounds_logged": 0, '
            '"last_reviewed_id": 0, "requested_changes": [], '
            '"spend": {"cost_usd": 0.3433209, "turns": 9, "duration_ms": 36315, "calls": 1, '
            '"models": ["claude-sonnet-5"], "input_tokens": 13, "output_tokens": 1159, '
            '"cache_creation_tokens": 42251, "cache_read_tokens": 241303, "ttft_ms": 5588, '
            '"duration_api_ms": 32189}}\n'
            "-->\n"
        )

    def test_a_run_with_a_discarded_call_writes_it_under_its_own_key_so_the_closing_invocation_reads_it(self) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO,
            issue=44,
            run=RunMother.awaiting_merge_after_discarding(DiscardedCallMother.of_a_failed_call()),
        )

        assert process.calls[1].stdin.endswith(
            '"last_reviewed_id": 0, "requested_changes": [], '
            '"discarded_call": {"step": "verify", "cause": "failed-call", "reason": "claude: command not found"}}\n'
            "-->\n"
        )

    def test_writing_the_same_run_that_is_already_there_issues_no_edit_call(self) -> None:
        process = self._process(body=_SUB1_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(repo=_REPO, issue=45, run=RunMother.awaiting_ci())

        assert len(process.calls) == 1

    def test_reading_and_writing_only_ever_name_the_one_issue_being_updated(self) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
            repo=_OTHER_REPO, issue=44, run=RunMother.implementing()
        )

        assert all("44" in call.argv for call in process.calls)
        assert all("45" not in call.argv for call in process.calls)

    def test_a_body_that_came_back_empty_is_rejected_before_the_edit_that_would_erase_the_prose(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps({"body": ""}), stderr=""))

        with pytest.raises(EmptyIssueBodyError):
            GhRunRepository(call=GhCallDoubles.wired(process)).write_run(
                repo=_REPO, issue=45, run=RunMother.awaiting_ci()
            )

        assert len(process.calls) == 1


class TestClearingTheExecutionStateBlock:
    @staticmethod
    def _process(*, body: str, edit_code: int = 0) -> ScriptedProcess:
        return ScriptedProcess(
            ProcessOutput(code=0, stdout=json.dumps({"body": body}), stderr=""),
            ProcessOutput(code=edit_code, stdout="", stderr=""),
        )

    def test_a_body_with_a_block_gets_it_removed_and_the_prose_around_it_survives_byte_for_byte(self) -> None:
        process = self._process(body=_SUB1_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).clear_run(repo=_REPO, issue=45)

        assert process.calls[1].stdin == (
            "INTENCION: hoy no hay forma de medir el formato nuevo sin crearlo\n"
            "ACEPTACION: el cuerpo se lee entero; los criterios llegan como lineas\n"
            "ACEPTACION: el bloque de estado se puede reescribir sin tocar lo de arriba\n"
            "SENAL: exenta - spike de medicion\n"
            "\n\n\n"
        )

    def test_a_body_with_no_block_yet_is_left_unchanged_and_issues_no_edit_call(self) -> None:
        process = self._process(body=_SUB2_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).clear_run(repo=_OTHER_REPO, issue=44)

        assert len(process.calls) == 1

    def test_reading_and_writing_only_ever_name_the_one_issue_being_cleared(self) -> None:
        process = self._process(body=_SUB1_BODY)

        GhRunRepository(call=GhCallDoubles.wired(process)).clear_run(repo=_REPO, issue=45)

        assert all("45" in call.argv for call in process.calls)
        assert all("44" not in call.argv for call in process.calls)


class TestWritingTheMacroStateLabel:
    def test_a_normal_transition_is_a_single_call_that_both_adds_and_removes(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert len(process.calls) == 1
        argv = Argv(process.calls[0].argv)
        assert argv.value_of("--add-label") == "estado:en-curso"
        assert argv.value_of("--remove-label") == "estado:pendiente"

    def test_the_only_issue_number_a_label_write_ever_names_is_the_one_being_transitioned(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert all("44" not in call.argv for call in process.calls)
        assert all("45" in call.argv for call in process.calls)

    def test_it_never_reads_or_writes_a_body_because_a_macro_transition_is_a_label_write_only(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert process.calls[0].argv[1:3] == ["issue", "edit"]
        assert "--body" not in process.calls[0].argv
        assert "--body-file" not in process.calls[0].argv
        assert "view" not in process.calls[0].argv

    def test_a_run_carrying_no_label_yet_is_edited_with_no_remove_flag_because_gh_refuses_an_absent_one(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=None, add=IssueLabel.IN_PROGRESS
        )

        assert len(process.calls) == 1
        assert Argv(process.calls[0].argv).value_of("--add-label") == "estado:en-curso"
        assert "--remove-label" not in process.calls[0].argv

    def test_asking_gh_to_remove_a_label_the_issue_never_carried_fails_and_creates_no_label(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(
                code=1,
                stdout="",
                stderr=(
                    "failed to update https://github.com/alcaptar/slice-runner/issues/45: "
                    "'estado:pendiente' not found\nfailed to update 1 issue\n"
                ),
            )
        )

        with pytest.raises(GhCommandFailedError, match="estado:pendiente"):
            GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
                repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
            )

        assert len(process.calls) == 1

    def test_a_label_missing_on_the_repo_is_created_once_and_the_edit_is_retried(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(
                code=1,
                stdout="",
                stderr=(
                    "failed to update https://github.com/alcaptar/slice-runner/issues/45: "
                    "'bloqueada:ci-roja' not found\nfailed to update 1 issue\n"
                ),
            ),
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=0, stdout="", stderr=""),
        )

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
        )

        assert len(process.calls) == 3
        assert process.calls[1].argv[:3] == ["gh", "label", "create"]
        assert process.calls[1].argv[3] == "bloqueada:ci-roja"
        assert Argv(process.calls[1].argv).value_of("--repo") == _REPO
        assert process.calls[2].argv == process.calls[0].argv

    def test_a_second_failure_after_creating_the_label_still_raises(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="'bloqueada:ci-roja' not found"),
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=1, stdout="", stderr="rate limited"),
        )

        with pytest.raises(GhCommandFailedError):
            GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
                repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
            )

    def test_a_failure_unrelated_to_a_missing_label_raises_without_trying_to_create_one(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="authentication required"))

        with pytest.raises(GhCommandFailedError):
            GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
                repo=_REPO, issue=45, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_RED
            )

        assert len(process.calls) == 1

    def test_a_transition_write_names_only_the_two_macro_labels_involved_so_a_foreign_label_survives(
        self,
    ) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_label(
            repo=_REPO, issue=45, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

        assert process.calls[0].argv == [
            "gh",
            "issue",
            "edit",
            "45",
            "--repo",
            _REPO,
            "--add-label",
            IssueLabel.IN_PROGRESS.value,
            "--remove-label",
            IssueLabel.PENDING.value,
        ], "the argv carries more than the two macro labels involved, which a foreign label would not survive"


class TestRemovingTheMacroStateLabel:
    def test_a_call_removes_the_label_named_and_adds_none_in_its_place(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).remove_label(
            repo=_REPO, issue=45, remove=IssueLabel.AWAITING_MERGE
        )

        assert len(process.calls) == 1
        argv = Argv(process.calls[0].argv)
        assert argv.value_of("--remove-label") == "estado:esperando-merge"
        assert "--add-label" not in process.calls[0].argv

    def test_the_only_issue_number_named_is_the_one_being_closed(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).remove_label(
            repo=_REPO, issue=45, remove=IssueLabel.AWAITING_MERGE
        )

        assert all("44" not in call.argv for call in process.calls)
        assert all("45" in call.argv for call in process.calls)

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="authentication required"))

        with pytest.raises(GhCommandFailedError, match="authentication required"):
            GhRunRepository(call=GhCallDoubles.wired(process)).remove_label(
                repo=_REPO, issue=45, remove=IssueLabel.AWAITING_MERGE
            )


class TestMarkingAnOrder:
    def test_the_call_is_a_comment_saying_which_order_was_given_and_with_what_text(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_order(
            repo=_REPO, issue=45, order=Order.RETRY, text="el control ya esta arreglado"
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert f"`{Order.RETRY}`" in process.calls[0].stdin
        assert "el control ya esta arreglado" in process.calls[0].stdin

    @pytest.mark.parametrize("order", list(Order))
    def test_the_comment_carries_none_of_the_tokens_the_run_used_to_read(self, order: Order) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_order(repo=_REPO, issue=45, order=order, text="x")

        assert not any(token in process.calls[0].stdin for token in ("-GO", "-REVIEW", "-RETRY"))

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_order(repo=_REPO, issue=45, order=Order.RETRY, text="")

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).mark_order(
                repo=_REPO, issue=45, order=Order.RETRY, text=""
            )


class TestReadingASubissueWhoseRunBlockWasWrittenByAnEarlierVersion:
    @staticmethod
    def _read(body: str) -> Run:
        payload = {**GhResponseMother.children_of_parent()[1], "body": body}
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

        subissue = GhRunRepository(call=GhCallDoubles.wired(process)).read_subissue(repo=_REPO, issue=49)
        assert subissue.run is not None

        return subissue.run

    @staticmethod
    def _with_keys_before_the_retry_instruction(keys: str) -> str:
        return _SUB1_BODY.replace('"retry_instruction": "", ', f'{keys}, "retry_instruction": "", ')

    def test_a_block_carrying_the_alignment_the_correction_and_the_understand_discards_is_read_without_them(
        self,
    ) -> None:
        keys = '"corrected": "falta la senal", "alignment": "agreed", "understand_discards": 2'

        assert self._read(self._with_keys_before_the_retry_instruction(keys)) == self._read(_SUB1_BODY)

    @pytest.mark.parametrize("pending", ["true", "false"])
    def test_a_block_carrying_the_retired_pending_flag_is_read_without_it(self, pending: str) -> None:
        keys = f'"understanding_pending": {pending}'

        assert self._read(self._with_keys_before_the_retry_instruction(keys)) == self._read(_SUB1_BODY)

    def test_a_retired_key_carrying_something_that_is_not_a_boolean_is_still_refused(self) -> None:
        body = self._with_keys_before_the_retry_instruction('"understanding_pending": "yes"')
        payload = {**GhResponseMother.children_of_parent()[1], "body": body}
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

        with pytest.raises(UnreadableRunError):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_subissue(repo=_REPO, issue=49)


class TestMarkingASliceReset:
    _AT = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
    _BRANCH = "slice/16-reseteo-de-una-slice"

    def test_the_call_is_a_comment_carrying_the_rendered_reset_notice(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_reset(
            repo=_REPO, issue=45, branch=self._BRANCH, at=self._AT
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert process.calls[0].stdin == ResetComment.rendered(branch=self._BRANCH, at=self._AT)

    def test_the_comment_names_the_branch_and_says_neither_it_nor_the_working_tree_were_touched(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_reset(
            repo=_REPO, issue=45, branch=self._BRANCH, at=self._AT
        )

        assert self._BRANCH in process.calls[0].stdin
        assert "arbol de trabajo" in process.calls[0].stdin

    def test_the_comment_carries_the_marker_that_lets_a_later_read_find_it_back(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_reset(
            repo=_REPO, issue=45, branch=self._BRANCH, at=self._AT
        )

        assert ResetComment.MARKER in process.calls[0].stdin

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).mark_reset(
            repo=_REPO, issue=45, branch=self._BRANCH, at=self._AT
        )

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).mark_reset(
                repo=_REPO, issue=45, branch=self._BRANCH, at=self._AT
            )


class TestFlaggingAPullRequestLeftUnmerged:
    def test_the_call_is_a_comment_naming_the_pull_request_left_unmerged(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).flag_unmerged_pull_request(
            repo=_REPO, issue=45, pull_request=61
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert "#61" in process.calls[0].stdin
        assert "borrador" in process.calls[0].stdin

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).flag_unmerged_pull_request(
            repo=_REPO, issue=45, pull_request=61
        )

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).flag_unmerged_pull_request(
                repo=_REPO, issue=45, pull_request=61
            )


class TestWritingWhyAPrecheckStoppedTheRun:
    def test_the_call_is_a_comment_naming_the_outcome_and_carrying_its_reason(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_precheck_reason(
            repo=_REPO,
            issue=45,
            outcome=PrecheckOutcome.UNREADABLE_SOURCE,
            reason="CLAUDE.md does not exist under the worktree",
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert PrecheckOutcome.UNREADABLE_SOURCE.value in process.calls[0].stdin
        assert "CLAUDE.md does not exist under the worktree" in process.calls[0].stdin

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).write_precheck_reason(
            repo=_REPO, issue=45, outcome=PrecheckOutcome.SOURCES_OVER_BUDGET, reason="over the budget"
        )

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).write_precheck_reason(
                repo=_REPO, issue=45, outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md missing"
            )


class TestClosingTheParent:
    def test_a_single_call_closes_the_issue_and_leaves_why_as_its_comment(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).close_parent(repo=_REPO, issue=43, subissue_count=4)

        assert len(process.calls) == 1
        argv = Argv(process.calls[0].argv)
        assert process.calls[0].argv[:4] == ["gh", "issue", "close", "43"]
        assert argv.value_of("--repo") == _REPO
        assert argv.value_of("--comment") == AutomationMark.appended_to(
            "Las 4 subissue(s) de esta feature estan todas cerradas, asi que esta feature se cierra con ellas."
        )

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="authentication required"))

        with pytest.raises(GhCommandFailedError, match="authentication required"):
            GhRunRepository(call=GhCallDoubles.wired(process)).close_parent(repo=_REPO, issue=43, subissue_count=4)


class TestPublishingTheVetoFindings:
    def test_the_call_is_a_comment_carrying_the_findings_as_stdin(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))
        history = FindingsHistoryMother.of_a_single_round(FindingMother.without_line())

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_findings(
            repo=_REPO, issue=45, history=history, debt=DeclaredDebt.nothing()
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert process.calls[0].stdin == VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

    def test_the_comment_carries_the_marker_that_lets_a_later_read_find_it_back(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_findings(
            repo=_REPO,
            issue=45,
            history=FindingsHistoryMother.of_a_single_round(FindingMother.without_line()),
            debt=DeclaredDebt.nothing(),
        )

        assert VetoFindingsComment.MARKER in process.calls[0].stdin

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_findings(
            repo=_REPO,
            issue=45,
            history=FindingsHistoryMother.of_a_single_round(FindingMother.without_line()),
            debt=DeclaredDebt.nothing(),
        )

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).publish_findings(
                repo=_REPO,
                issue=45,
                history=FindingsHistoryMother.of_a_single_round(FindingMother.without_line()),
                debt=DeclaredDebt.nothing(),
            )


class TestPublishingTheCatchUpConflict:
    def test_the_call_is_a_comment_carrying_the_conflicting_paths_as_stdin(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))
        paths = ("shared.txt", "src/module.py")

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_catch_up_conflict(repo=_REPO, issue=45, paths=paths)

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert process.calls[0].stdin == CatchUpConflictComment.rendered(paths)

    def test_the_comment_names_every_conflicting_path(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))
        paths = ("shared.txt", "src/module.py")

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_catch_up_conflict(repo=_REPO, issue=45, paths=paths)

        assert "shared.txt" in process.calls[0].stdin
        assert "src/module.py" in process.calls[0].stdin

    def test_the_comment_carries_the_visible_automation_mark(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_catch_up_conflict(
            repo=_REPO, issue=45, paths=("shared.txt",)
        )

        assert AutomationMark.TEXT in process.calls[0].stdin

    def test_a_non_zero_exit_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 422: Unprocessable Entity"))

        with pytest.raises(GhCommandFailedError, match="HTTP 422"):
            GhRunRepository(call=GhCallDoubles.wired(process)).publish_catch_up_conflict(
                repo=_REPO, issue=45, paths=("shared.txt",)
            )


class TestFindingAVetoFinding:
    @staticmethod
    def _process(bodies: list[str]) -> ScriptedProcess:
        template = GhResponseMother.subissue_comments()[0]
        payload = {"comments": [{**template, "body": body} for body in bodies]}

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    def test_a_finding_is_located_by_its_id_from_the_comment_alone_with_no_verdict_object_in_sight(self) -> None:
        finding = FindingMother.without_line()
        process = self._process(
            [VetoFindingsComment.rendered(FindingsHistoryMother.of_a_single_round(finding), DeclaredDebt.nothing())]
        )

        located = GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f1")

        assert located == finding

    def test_no_veto_findings_comment_published_yet_resolves_to_none(self) -> None:
        process = self._process(["un comentario cualquiera"])

        located = GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f1")

        assert located is None

    def test_an_unknown_id_inside_a_published_comment_resolves_to_none(self) -> None:
        process = self._process(
            [
                VetoFindingsComment.rendered(
                    FindingsHistoryMother.of_a_single_round(FindingMother.without_line()), DeclaredDebt.nothing()
                )
            ]
        )

        located = GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f9")

        assert located is None

    def test_publishing_a_new_verdict_makes_the_latest_comment_the_only_one_that_resolves_an_id(self) -> None:
        old = FindingsHistoryMother.of_a_single_round(FindingMother.without_line(), FindingMother.low_severity())
        new_finding = FindingMother.with_line()
        new = FindingsHistoryMother.of_a_single_round(new_finding)
        process = self._process(
            [
                VetoFindingsComment.rendered(old, DeclaredDebt.nothing()),
                VetoFindingsComment.rendered(new, DeclaredDebt.nothing()),
            ]
        )

        located = GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f1")

        assert located == new_finding

    def test_an_id_that_only_a_prior_verdict_published_stops_resolving_once_a_new_one_is_published(self) -> None:
        old = FindingsHistoryMother.of_a_single_round(FindingMother.without_line(), FindingMother.low_severity())
        new = FindingsHistoryMother.of_a_single_round(FindingMother.with_line())
        process = self._process(
            [
                VetoFindingsComment.rendered(old, DeclaredDebt.nothing()),
                VetoFindingsComment.rendered(new, DeclaredDebt.nothing()),
            ]
        )

        located = GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f2")

        assert located is None

    def test_a_findings_block_that_is_not_valid_json_is_rejected_as_unreadable(self) -> None:
        malformed = f"{VetoFindingsComment.MARKER}\n<!-- slice-runner:hallazgos-json\n{{not json}}\n-->"
        process = self._process([malformed])

        with pytest.raises(UnreadableFindingsError):
            GhRunRepository(call=GhCallDoubles.wired(process)).find_finding(repo=_REPO, issue=45, finding_id="f1")


class TestGhFailuresAreInterpretedNotSwallowed:
    def test_a_non_zero_exit_reading_the_parent_raises_with_the_stderr_it_carried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 404: Not Found"))

        with pytest.raises(GhCommandFailedError, match="HTTP 404"):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=999, slice_repo=None)

    def test_a_response_that_is_not_json_is_rejected_instead_of_crashing_on_a_decode_error(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="not json at all", stderr=""))

        with pytest.raises(UnreadableIssueError):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)


class TestGhRunRepositoryRetryingTransientFailures:
    def test_a_transient_failure_reading_the_parent_is_retried_until_it_succeeds(self) -> None:
        recorded = GhResponseMother.parent_with_two_children()
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="connection reset by peer"),
            ProcessOutput(code=0, stdout=json.dumps(recorded), stderr=""),
        )

        parent = GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.subissue_count == 2
        assert len(process.calls) == 2

    def test_a_non_transient_failure_still_fails_on_the_first_attempt(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="HTTP 404: Not Found"))

        with pytest.raises(GhCommandFailedError):
            GhRunRepository(call=GhCallDoubles.wired(process)).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert len(process.calls) == 1

    def test_an_unsafe_write_that_fails_transiently_is_not_retried(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=1, stdout="", stderr="connection reset by peer"))

        with pytest.raises(GhCommandFailedError):
            GhRunRepository(call=GhCallDoubles.wired(process)).mark_order(
                repo=_REPO, issue=45, order=Order.RETRY, text="x"
            )

        assert len(process.calls) == 1

    def test_the_reason_names_how_many_times_it_retried_before_giving_up(self) -> None:
        budgets = Budgets(gh_retries=1)
        process = ScriptedProcess(
            ProcessOutput(code=1, stdout="", stderr="connection reset by peer"),
            ProcessOutput(code=1, stdout="", stderr="connection reset by peer"),
        )

        with pytest.raises(GhCommandFailedError, match="retried 1x"):
            GhRunRepository(call=GhCallDoubles.wired(process, budgets=budgets)).read_parent(
                repo=_REPO, issue=43, slice_repo=None
            )

        assert len(process.calls) == 2


class TestReadingTheHeadingOfEachSubissue:
    @staticmethod
    def _process(*, children: list[dict[str, object]] | None = None) -> ScriptedProcess:
        payload = children if children is not None else GhResponseMother.children_of_parent()

        return ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

    @staticmethod
    def _single_child(title: str) -> list[dict[str, object]]:
        return [{"number": 1, "title": title, "body": "", "labels": [], "state": "OPEN"}]

    def test_the_name_in_parentheses_of_the_title_becomes_the_name_of_the_slice(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].slice_id.name == "primera-de-prueba"
        assert by_slice["slice-02"].slice_id.name == "segunda-de-prueba"

    def test_what_the_title_says_after_the_name_becomes_the_summary_of_the_slice(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        by_slice = {child.slice_id.canonical: child for child in children}
        assert by_slice["slice-01"].summary == "la que se creo despues"

    def test_the_name_and_the_number_of_the_slice_are_the_branch_the_run_will_stand_on(self) -> None:
        children = GhRunRepository(call=GhCallDoubles.wired(self._process())).read_children(
            repo=_REPO, parent=43, expected=2
        )

        assert children[0].branch == "slice/01-primera-de-prueba"

    def test_a_title_with_the_identifier_but_no_name_is_rejected_instead_of_branching_namelessly(self) -> None:
        nameless = [{"number": 1, "title": "slice-01: no name at all", "body": "", "labels": [], "state": "OPEN"}]

        with pytest.raises(UnreadableIssueError, match="slice-NN"):
            GhRunRepository(call=GhCallDoubles.wired(self._process(children=nameless))).read_children(
                repo=_REPO, parent=43, expected=1
            )

    def test_a_title_carrying_a_user_story_key_composes_the_canonical_identifier_with_it(self) -> None:
        keyed = self._single_child("PROJ-1234 slice-01 (name): resumen")

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=keyed))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].slice_id == SliceIdentity(ordinal=1, name="name", user_story="PROJ-1234")
        assert children[0].slice_id.canonical == "PROJ-1234-01"

    def test_a_title_with_no_key_composes_the_canonical_identifier_as_slice_nn(self) -> None:
        unkeyed = self._single_child("slice-01 (name): resumen")

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=unkeyed))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].slice_id == SliceIdentity(ordinal=1, name="name", user_story=None)
        assert children[0].slice_id.canonical == "slice-01"

    def test_the_branch_of_a_keyed_slice_carries_the_key_before_the_ordinal(self) -> None:
        keyed = self._single_child("PROJ-1234 slice-01 (name): resumen")

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=keyed))).read_children(
            repo=_REPO, parent=43, expected=1
        )

        assert children[0].branch == "slice/PROJ-1234-01-name"

    def test_a_prefix_that_is_not_a_recognizable_key_is_rejected_instead_of_folded_into_the_name(self) -> None:
        malformed = self._single_child("proj-1234 slice-01 (name): resumen")

        with pytest.raises(UnreadableIssueError, match="slice-NN"):
            GhRunRepository(call=GhCallDoubles.wired(self._process(children=malformed))).read_children(
                repo=_REPO, parent=43, expected=1
            )

    def test_a_single_digit_ordinal_is_rejected_instead_of_silently_zero_padded(self) -> None:
        single_digit = self._single_child("slice-1 (name): resumen")

        with pytest.raises(UnreadableIssueError, match="slice-NN"):
            GhRunRepository(call=GhCallDoubles.wired(self._process(children=single_digit))).read_children(
                repo=_REPO, parent=43, expected=1
            )

    def test_ordering_is_by_the_ordinal_and_not_by_the_composed_canonical_string(self) -> None:
        out_of_order = [
            {
                "number": 1,
                "title": "KEY-9 slice-02 (b): later slice, keyed but sorts first alphabetically",
                "body": "",
                "labels": [],
                "state": "OPEN",
            },
            {
                "number": 2,
                "title": "slice-01 (a): earlier slice, unkeyed but sorts last alphabetically",
                "body": "",
                "labels": [],
                "state": "OPEN",
            },
        ]

        children = GhRunRepository(call=GhCallDoubles.wired(self._process(children=out_of_order))).read_children(
            repo=_REPO, parent=43, expected=2
        )

        assert [child.slice_id.canonical for child in children] == ["slice-01", "KEY-9-02"]


class TestPublishingAKeptWorktree:
    def test_the_call_is_a_comment_carrying_the_path_and_the_reason_as_stdin(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GhRunRepository(call=GhCallDoubles.wired(process)).publish_kept_worktree(
            repo=_REPO, issue=45, path="/clone/.worktrees/05-x", retirement=WorktreeRetirement.KEPT_UNCOMMITTED_WORK
        )

        assert process.calls[0].argv == ["gh", "issue", "comment", "45", "--repo", _REPO, "--body-file", "-"]
        assert "`/clone/.worktrees/05-x`" in process.calls[0].stdin
        assert "cambios sin comitear" in process.calls[0].stdin
