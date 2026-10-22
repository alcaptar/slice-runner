from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import (
    InvalidImplementationReportError,
    MissingStructuredOutputError,
    PermissionDeniedError,
)
from slice_runner.domain.path_kind import PathKind
from slice_runner.infrastructure.claude_implementer import ClaudeImplementer
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import (
    RecordedActivityLog,
    RecordedProcess,
    RecordedSourceReader,
    RecordedSpendLog,
    RecordedToolUseRecorder,
    RecordedTrace,
    RecordedTurnLog,
    StreamingProcess,
)
from slice_runner.tests.mothers.assignment_mother import AssignmentMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.implementation import Implementation
    from slice_runner.infrastructure.process import Process

_RECORDED = "implementer-two-paths"


class Calling:
    @staticmethod
    def _calls(
        process: Process,
        *,
        trace: RecordedTrace | None = None,
        tool_uses: RecordedToolUseRecorder | None = None,
    ) -> HarnessInvocationRunner:
        return HarnessInvocationRunner(
            process=process,
            telemetry=HarnessTelemetry(
                trace=trace or RecordedTrace(),
                turns=RecordedTurnLog(),
                activity=RecordedActivityLog(),
                spend_log=RecordedSpendLog(),
                tool_uses=tool_uses or RecordedToolUseRecorder(),
            ),
        )


class OneRound(Calling):
    @classmethod
    def implemented(cls, process: Process) -> Implementation:
        return ClaudeImplementer(calls=cls._calls(process), reader=RecordedSourceReader()).implement(
            AssignmentMother.of_the_first_round()
        )


class TestHowTheImplementerIsInvoked:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(
            ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=RecordedSourceReader()).argv
        )

    def test_it_runs_with_bypassed_permissions_because_it_writes_and_runs_commands(self, argv: Argv) -> None:
        assert argv.value_of("--permission-mode") == "bypassPermissions"

    def test_the_model_is_fixed_and_not_inherited_from_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--model") == "claude-sonnet-5-5"

    def test_the_effort_is_fixed_and_not_read_from_the_settings_of_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--effort") == "high"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Write,Edit,Bash,Grep,Glob,Skill"

    def test_skill_is_granted_because_the_brief_loads_the_methodology_skill(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")
        assert "test-driven-development" in SliceImplementerBrief.TEXT

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_only_user_settings_load_so_the_destination_repo_does_not_pay_its_own_claude_md(self, argv: Argv) -> None:
        assert argv.value_of("--setting-sources") == "user"

    def test_the_streamed_envelope_of_the_harness_is_asked_for_so_its_turns_can_be_watched_as_they_happen(
        self, argv: Argv
    ) -> None:
        assert argv.value_of("--output-format") == "stream-json"
        assert argv.contains("--verbose")

    def test_the_schema_that_travels_is_flat_with_the_enum_and_the_nested_object_resolved(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == {
            "additionalProperties": False,
            "properties": {
                "paths": {
                    "items": {
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string"},
                            "kind": {"enum": ["production", "test"], "type": "string"},
                        },
                        "required": ["path", "kind"],
                        "type": "object",
                    },
                    "type": "array",
                },
                "left_out": {"items": {"type": "string"}, "type": "array"},
                "deviations": {"items": {"type": "string"}, "type": "array"},
            },
            "required": ["paths", "left_out", "deviations"],
            "type": "object",
        }

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []

    def test_the_brief_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        invocation = ImplementerInvocation(
            assignment=AssignmentMother.of_the_first_round(), reader=RecordedSourceReader()
        )

        assert SliceImplementerBrief.TEXT in invocation.text
        assert invocation.text not in invocation.argv

    def test_the_cwd_the_process_needs_travels_with_the_invocation_and_not_only_as_a_bare_repo(self) -> None:
        assert (
            ImplementerInvocation(assignment=AssignmentMother.of_the_first_round(), reader=RecordedSourceReader()).cwd
            == AssignmentMother.WORKTREE
        )


class TestWhereTheProcessRuns(Calling):
    def test_the_worktree_becomes_the_working_directory_of_the_process_and_not_only_prompt_text(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=self._calls(process), reader=RecordedSourceReader()).implement(
            AssignmentMother.of_the_first_round()
        )

        assert process.cwd == AssignmentMother.WORKTREE

    def test_the_harness_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=self._calls(process), reader=RecordedSourceReader()).implement(
            AssignmentMother.of_the_first_round()
        )

        assert process.calls == 1


class TestTheCallSubjectComesFromTheAssignmentsOwnFields(Calling):
    def test_the_trace_carries_the_assignments_own_repo_issue_and_slice_id_and_not_a_crossed_field(self) -> None:
        trace = RecordedTrace()
        assignment = AssignmentMother.of_the_first_round()

        ClaudeImplementer(
            calls=self._calls(RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED)), trace=trace),
            reader=RecordedSourceReader(),
        ).implement(assignment)

        recorded = trace.calls[0]
        assert (recorded.coordinates.repo, recorded.coordinates.issue, recorded.coordinates.slice_id.text) == (
            assignment.repo,
            assignment.issue,
            assignment.slice_id,
        )

    def test_the_tool_use_recording_carries_the_assignments_own_worktree_and_slice_id(self) -> None:
        tool_uses = RecordedToolUseRecorder()
        assignment = AssignmentMother.of_the_first_round()

        ClaudeImplementer(
            calls=self._calls(RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED)), tool_uses=tool_uses),
            reader=RecordedSourceReader(),
        ).implement(assignment)

        recorded = tool_uses.calls[0]
        assert (recorded.worktree, recorded.slice_id) == (assignment.worktree, assignment.slice_id)


class TestTheSliceDataThatTravelsWithTheBrief(Calling):
    @classmethod
    def _sent(cls, assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=cls._calls(process), reader=RecordedSourceReader()).implement(assignment)

        return process.stdin

    @staticmethod
    def _data(sent: str) -> str:
        match = re.match(
            r'<datos_de_la_slice id="([0-9a-f]{8})">\n(.*)\n</datos_de_la_slice id="\1">\n', sent, re.DOTALL
        )
        assert match is not None
        return match.group(2)

    def test_the_data_of_the_slice_open_the_prompt_inside_their_tag_and_the_methodology_follows_it(self) -> None:
        sent = self._sent(AssignmentMother.of_the_first_round())

        assert sent.startswith("<datos_de_la_slice id=")
        assert sent.endswith(SliceImplementerBrief.TEXT)

    def test_the_tag_id_is_the_first_eight_hex_characters_of_the_sha256_of_the_content_and_opens_and_closes_it(
        self,
    ) -> None:
        sent = self._sent(AssignmentMother.of_the_first_round())
        data = self._data(sent)
        identifier = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8]

        assert sent.startswith(
            f'<datos_de_la_slice id="{identifier}">\n{data}\n</datos_de_la_slice id="{identifier}">\n'
        )

    def test_the_methodology_names_the_tag_and_never_says_the_data_come_last(self) -> None:
        said = " ".join(SliceImplementerBrief.TEXT.split())

        assert "<datos_de_la_slice>" in said
        assert "al final de este prompt" not in said
        assert "## Datos de la slice" not in said

    def test_a_first_round_says_which_slice_of_which_issue_it_is_and_everything_the_slice_declared(self) -> None:
        assert self._data(self._sent(AssignmentMother.of_the_first_round())) == (
            "- issue: #45\n"
            "- slice: slice-05\n"
            "- repo: alcaptar/slice-runner\n"
            "- ruta del repo: /repos/slice-runner\n"
            "- intencion: hoy nada evita reimplementar una slice ya entregada\n"
            "- senal: exenta - este repo no despliega\n"
            "- excluye: \n"
            "- sustituye: \n"
            "- criterios de aceptacion (2):\n"
            "  - antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "  - cada precheck falla con un motivo distinguible, no con un booleano\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "    reglas del repo\n"
            "- controles del repo (1):\n"
            "  - lint: make linting\n"
            "- hallazgos de la vuelta anterior: ninguno, esta es la primera"
        )

    def test_a_slice_that_declares_something_excluded_carries_it_in_the_excluye_line(self) -> None:
        assert "- excluye: el panel de grafana que consume esta serie\n" in self._sent(
            AssignmentMother.of_a_slice_that_excludes_something()
        )

    def test_a_slice_that_declares_something_it_replaces_carries_it_in_the_sustituye_line(self) -> None:
        assert "- sustituye: si - el adaptador viejo; apagando el flag\n" in self._sent(
            AssignmentMother.of_a_slice_that_replaces_something()
        )

    def test_a_slice_with_a_user_story_names_the_slice_by_its_canonical_identifier_not_the_bare_ordinal(self) -> None:
        assert "- slice: PROJ-1234-05\n" in self._sent(
            AssignmentMother.of_the_first_round_of_a_slice_with_a_user_story()
        )

    def test_a_second_round_carries_every_finding_with_where_it_was_raised_and_why(self) -> None:
        assert self._data(self._sent(AssignmentMother.of_a_second_round())).endswith(
            "- hallazgos de la vuelta anterior (1):\n"
            "  - [medium] convenciones en src/x.py:42: prose in a `.py` "
            "(detalle: the why lives in the pull request body)"
        )

    def test_a_round_that_comes_back_from_red_controls_carries_the_path_of_the_log_and_never_its_output(self) -> None:
        assert self._data(self._sent(AssignmentMother.of_a_round_after_red_controls())).endswith(
            "- logs de los controles en rojo (1):\n  - /tmp/slice-runner/logs/lint.log"
        )

    def test_a_round_refused_for_a_dirty_index_says_so_and_names_the_files_that_were_not_declared(self) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_a_dirty_index())

        assert "la vuelta anterior no llego a medirse" in sent
        assert "src/leftover.py (not-declared)" in sent
        assert "declara en tu informe TODO fichero que toques" in sent

    def test_a_round_that_measured_carries_no_refusal_because_there_was_nothing_to_refuse(self) -> None:
        assert "no llego a medirse" not in self._sent(AssignmentMother.of_the_first_round())

    def test_a_repo_exempt_from_controls_carries_its_reason_and_no_command_to_run(self) -> None:
        assert "- controles del repo: ninguno - la integracion continua solo publica en master\n" in self._sent(
            AssignmentMother.of_a_repo_exempt_from_controls()
        )

    def test_a_round_after_a_dead_call_says_so_and_names_every_file_the_worktree_brought_dirty(self) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_a_dead_call())

        assert "la vuelta anterior murio sin informe legible" in sent
        assert "src/leftover.py" in sent
        assert "src/removed.py" in sent

    def test_a_first_round_carries_no_mention_of_a_dead_call_because_there_was_no_previous_call(self) -> None:
        assert "murio sin informe legible" not in self._sent(AssignmentMother.of_the_first_round())

    def test_a_round_with_staged_files_names_each_one_and_asks_to_declare_them_all_because_they_cannot_be_unstaged(
        self,
    ) -> None:
        data = self._data(self._sent(AssignmentMother.of_a_round_after_a_retry_with_staged_files()))

        assert (
            "- ficheros ya en el indice:\n"
            "  - src/kept.py\n"
            "  - src/tests/test_kept.py\n"
            "  - estan en el indice y no los puedes sacar: declaralos todos en tu informe"
        ) in data

    def test_a_round_with_nothing_staged_carries_no_section_about_the_index(self) -> None:
        assert "ficheros ya en el indice" not in self._sent(AssignmentMother.of_the_first_round())


class TestTheDesignDecisionsThatTravelWithTheBrief(Calling):
    @classmethod
    def _sent(cls, assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=cls._calls(process), reader=RecordedSourceReader()).implement(assignment)

        return process.stdin

    def test_the_decisions_of_the_parent_and_then_those_of_the_subissue_appear_in_that_order_under_their_section(
        self,
    ) -> None:
        sent = self._sent(AssignmentMother.of_the_first_round_with_decisions())

        section = sent[sent.index("\n## Decisiones de diseno\n") :]
        positions = [section.index(decision) for decision in AssignmentMother.DECISIONS]
        assert positions == sorted(positions)

    def test_each_decision_is_a_line_of_the_list(self) -> None:
        sent = self._sent(AssignmentMother.of_the_first_round_with_decisions())

        assert all(f"\n- {decision}" in sent for decision in AssignmentMother.DECISIONS)

    def test_the_prompt_no_longer_carries_the_agreed_understanding_section(self) -> None:
        sent = self._sent(AssignmentMother.of_the_first_round_with_decisions())

        assert "## Entendimiento acordado" not in sent

    def test_a_slice_without_decisions_carries_no_section_instead_of_an_empty_one(self) -> None:
        assert "\n## Decisiones de diseno\n" not in self._sent(AssignmentMother.of_the_first_round())


class TestTheRetryInstructionThatTravelsWithTheBrief(Calling):
    @classmethod
    def _sent(cls, assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=cls._calls(process), reader=RecordedSourceReader()).implement(assignment)

        return process.stdin

    def test_the_instruction_that_reopened_the_slice_travels_and_closes_the_prompt(self) -> None:
        assert self._sent(AssignmentMother.of_a_round_after_reopening()).endswith(AssignmentMother.RETRY_INSTRUCTION)

    def test_a_round_with_no_reopening_carries_no_section_instead_of_an_empty_one(self) -> None:
        assert "\n## Instruccion de reintento\n" not in self._sent(AssignmentMother.of_the_first_round())

    def test_the_instruction_goes_after_the_methodology_and_outside_the_tag_of_the_data(self) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_reopening())

        assert sent.index(SliceImplementerBrief.TEXT) < sent.index("\n## Instruccion de reintento\n")
        assert sent.index("\n## Instruccion de reintento\n") > sent.index("</datos_de_la_slice id=")

    def test_with_a_reopening_and_a_review_the_instruction_comes_first_and_the_requested_change_closes_the_prompt(
        self,
    ) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_reopening_and_a_review())

        assert sent.index(SliceImplementerBrief.TEXT) < sent.index("\n## Instruccion de reintento\n")
        assert sent.index("\n## Instruccion de reintento\n") < sent.index(
            "\n## Peticion de cambio en la pull request\n"
        )
        assert sent.endswith(AssignmentMother.REVIEW)


class TestWhatTheBriefSaysAboutWhoRunsTheControls:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceImplementerBrief.TEXT.split())

    def test_it_says_the_program_runs_them_so_repeating_the_whole_suite_adds_no_guarantee(self) -> None:
        assert "Quien ejecuta esos comandos y decide con ellos es el programa, no tu" in self._said()

    def test_it_does_not_claim_running_the_controls_is_what_bash_is_granted_for(self) -> None:
        assert "correr el ciclo TDD sobre lo que estas tocando" in self._said()
        assert "correr el ciclo TDD y los controles del repo" not in self._said()

    def test_it_warns_that_a_pipe_answers_with_the_exit_code_of_the_last_stage_and_not_of_the_command(self) -> None:
        assert "el codigo de salida que ves es el del ultimo tramo, no el del comando" in self._said()

    def test_it_still_forbids_tuning_the_control_commands_now_that_it_says_who_runs_them(self) -> None:
        assert "no se cambian ni se afinan para que pasen" in self._said()


class TestWhatTheBriefSaysAboutExcludes:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceImplementerBrief.TEXT.split())

    def test_it_tells_the_implementer_not_to_build_what_the_line_names_as_out_of_scope(self) -> None:
        assert "quien corto esta slice decidio dejar fuera de su alcance a proposito: no lo construyas" in self._said()

    def test_it_tells_the_implementer_to_declare_a_necessary_exclusion_as_left_out_instead_of_building_it(
        self,
    ) -> None:
        assert (
            "resulta necesario para cumplir un criterio de aceptacion, declaralo en `left_out` en vez de "
            "construirlo por tu cuenta" in self._said()
        )


class TestWhatTheBriefSaysAboutFinishingWhatWasAsked:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceImplementerBrief.TEXT.split())

    def test_it_opens_a_paragraph_telling_the_implementer_to_stop_once_what_was_asked_is_done(self) -> None:
        assert "**Cuando lo pedido esta hecho, paras.**" in self._said()

    def test_it_opens_a_paragraph_telling_the_implementer_to_keep_going_until_every_criterion_is_met(self) -> None:
        assert "**Acabas lo pedido.**" in self._said()

    def test_it_no_longer_carries_the_rule_the_scope_paragraph_replaces(self) -> None:
        assert "No sobredimensiones" not in self._said()


class TestWhatTheBriefSaysAboutReplaces:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceImplementerBrief.TEXT.split())

    def test_it_tells_the_implementer_to_apply_the_pattern_the_line_declares(self) -> None:
        assert "aplicalo tal como lo declara la linea" in self._said()

    def test_it_tells_the_implementer_to_declare_a_different_pattern_as_left_out_instead_of_changing_it(
        self,
    ) -> None:
        assert "no lo cambies por tu cuenta: implementa el que la linea pide y declaralo en `left_out`" in self._said()


class TestWhatTheBriefSaysAboutDesignDecisions:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceImplementerBrief.TEXT.split())

    def test_it_names_the_section_that_carries_the_decisions(self) -> None:
        assert '**"## Decisiones de diseno"**' in self._said()

    def test_it_says_the_decisions_are_binding_and_are_not_reopened_on_the_implementers_own(self) -> None:
        assert "Son **vinculantes**" in self._said()
        assert "no se reabre por tu cuenta" in self._said()

    def test_it_tells_the_implementer_to_decide_and_declare_in_deviations_when_the_real_code_prevents_a_decision(
        self,
    ) -> None:
        assert "si el codigo real impide cumplir una decision, decides tu y lo declaras en `deviations`" in self._said()

    def test_it_no_longer_talks_about_the_agreed_understanding(self) -> None:
        assert "Entendimiento acordado" not in self._said()


class TestThePendingReviewsThatTravelWithTheBrief(Calling):
    @classmethod
    def _sent(cls, assignment: Assignment) -> str:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        ClaudeImplementer(calls=cls._calls(process), reader=RecordedSourceReader()).implement(assignment)

        return process.stdin

    def test_the_body_of_the_review_that_ordered_the_correction_travels_and_closes_the_prompt(self) -> None:
        assert self._sent(AssignmentMother.of_a_round_after_a_review()).endswith(AssignmentMother.REVIEW)

    def test_a_round_with_no_pending_review_carries_no_section_instead_of_an_empty_one(self) -> None:
        assert "\n## Peticion de cambio en la pull request\n" not in self._sent(AssignmentMother.of_the_first_round())

    def test_an_anchored_comment_reaches_the_implementer_with_its_file_and_its_line(self) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_a_review_with_an_anchored_comment())

        assert sent.endswith(
            f"{PullRequestReviewCommentMother.PATH}:{PullRequestReviewCommentMother.LINE}: "
            f"{PullRequestReviewCommentMother.ANCHORED_BODY}"
        )

    def test_a_stale_comment_with_no_line_reaches_the_implementer_with_only_its_file_instead_of_breaking(
        self,
    ) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_a_stale_review_comment())

        assert sent.endswith(f"{PullRequestReviewCommentMother.PATH}: {PullRequestReviewCommentMother.STALE_BODY}")

    def test_the_body_and_the_anchored_comment_of_the_same_review_both_reach_the_implementer(self) -> None:
        sent = self._sent(AssignmentMother.of_a_round_after_a_review_with_a_body_and_an_anchored_comment())

        assert sent.endswith(
            f"{AssignmentMother.REVIEW}\n\n"
            f"{PullRequestReviewCommentMother.PATH}:{PullRequestReviewCommentMother.LINE}: "
            f"{PullRequestReviewCommentMother.ANCHORED_BODY}"
        )


class TestTheReportOfARecordedCall:
    def test_both_paths_of_the_recorded_call_arrive_labelled(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert [(reported.path, reported.kind) for reported in report.paths] == [
            ("hello.py", PathKind.PRODUCTION),
            ("test_hello.py", PathKind.TEST),
        ]

    def test_a_report_with_nothing_left_out_carries_an_empty_tuple(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert report.left_out == ()

    def test_what_was_left_out_travels_whole_one_entry_per_thing(self) -> None:
        left_out: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "production"}, {"path": "test_hello.py", "kind": "test"}],
            "left_out": [
                "el cableado del subcomando de metrics queda para otra slice",
                "no se anadio retry al cliente de gh",
            ],
            "deviations": [],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(left_out, recorded=_RECORDED))

        report = OneRound.implemented(process)

        assert report.left_out == (
            "el cableado del subcomando de metrics queda para otra slice",
            "no se anadio retry al cliente de gh",
        )

    def test_a_report_with_no_deviations_carries_an_empty_tuple(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert report.deviations == ()

    def test_the_deviations_travel_whole_one_entry_per_decision_not_followed(self) -> None:
        deviating: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "production"}, {"path": "test_hello.py", "kind": "test"}],
            "left_out": [],
            "deviations": [
                "el puerto no admite la firma decidida porque ya la consume otro adaptador",
                "la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza",
            ],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(deviating, recorded=_RECORDED))

        report = OneRound.implemented(process)

        assert report.deviations == (
            "el puerto no admite la firma decidida porque ya la consume otro adaptador",
            "la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza",
        )

    def test_what_the_harness_spent_on_the_call_travels_with_the_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(_RECORDED))

        report = OneRound.implemented(process)

        assert report.spend == HarnessSpendMother.of_the_implementer_call()

    def test_a_background_task_that_ends_after_the_result_does_not_bury_it(self) -> None:
        process = StreamingProcess(HarnessEnvelopeMother.streamed_then_a_background_task_ends())

        implementation = OneRound.implemented(process)

        assert implementation.paths
        assert implementation.spend.cost_usd > 0


class TestANonEmptyPermissionDenialsFailsTheCall:
    def test_a_denied_read_raises_instead_of_returning_a_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError):
            OneRound.implemented(process)

    def test_the_error_names_which_permission_was_denied(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError, match=f"Read {HarnessEnvelopeMother.DENIED_READ}"):
            OneRound.implemented(process)

    def test_what_the_denied_call_spent_survives_the_rejection(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read_over(_RECORDED))

        with pytest.raises(PermissionDeniedError) as rejection:
            OneRound.implemented(process)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()


class TestWhatTheImplementerIsAllowedToReturn:
    def test_a_report_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="left_out"):
            OneRound.implemented(process)

    def test_a_report_without_deviations_is_rejected_instead_of_read_as_having_none(self) -> None:
        without_deviations: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "production"}],
            "left_out": [],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(without_deviations, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="deviations"):
            OneRound.implemented(process)

    def test_a_rejected_report_still_reports_what_the_call_spent(self) -> None:
        incomplete: dict[str, object] = {"paths": [{"path": "hello.py", "kind": "production"}]}
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incomplete, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError) as rejection:
            OneRound.implemented(process)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()

    def test_an_envelope_without_structured_output_is_rejected_instead_of_treated_as_an_empty_report(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.without_structured_output(recorded=_RECORDED))

        with pytest.raises(MissingStructuredOutputError):
            OneRound.implemented(process)

    def test_the_rejection_of_a_missing_structured_output_still_reports_what_the_call_spent(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.without_structured_output(recorded=_RECORDED))

        with pytest.raises(MissingStructuredOutputError) as rejection:
            OneRound.implemented(process)

        assert rejection.value.spend == HarnessSpendMother.of_the_implementer_call()

    def test_a_path_kind_outside_the_vocabulary_is_rejected_saying_which_one_it_was(self) -> None:
        invented_kind: dict[str, object] = {
            "paths": [{"path": "hello.py", "kind": "documentation"}],
            "left_out": [],
            "deviations": [],
        }
        process = RecordedProcess(HarnessEnvelopeMother.carrying(invented_kind, recorded=_RECORDED))

        with pytest.raises(InvalidImplementationReportError, match="'documentation'"):
            OneRound.implemented(process)
