from __future__ import annotations

import hashlib
import json
import re

import pytest

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge
from slice_runner.infrastructure.verdict_payload import VerdictPayload
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import RecordedSourceReader
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.verdict_mother import FindingMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

_JUDGE = JudgeMother.reading_the_repo_and_its_yardstick()
_READER = RecordedSourceReader()


class TestWhereTheProcessRuns:
    def test_the_cwd_the_process_needs_is_the_worktree_of_the_slice_under_review(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        assert JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).cwd == review.worktree


class TestWhatTheJudgeIsGranted:
    @pytest.fixture
    def argv(self) -> Argv:
        return Argv(
            JudgeInvocation(
                judge=JudgeMother.reading_the_repo_and_its_yardstick(),
                review=SliceUnderReviewMother.of_the_slice(),
                reader=_READER,
            ).argv
        )

    def test_the_model_is_fixed_and_not_inherited_from_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--model") == "claude-opus-5-5"

    def test_the_effort_is_fixed_and_not_read_from_the_settings_of_whoever_launches_the_run(self, argv: Argv) -> None:
        assert argv.value_of("--effort") == "high"

    def test_the_tools_travel_in_a_single_comma_separated_argument(self, argv: Argv) -> None:
        assert argv.value_of("--tools") == "Read,Grep,Glob,Skill"

    def test_the_judge_gets_skill_because_two_items_of_his_rubric_load_one(self, argv: Argv) -> None:
        assert "Skill" in argv.value_of("--tools").split(",")

    def test_no_writing_or_running_tools_because_the_one_who_verifies_does_not_implement(self, argv: Argv) -> None:
        granted = set(argv.value_of("--tools").split(","))

        assert granted.isdisjoint({"Bash", "Write", "Edit"})

    def test_the_only_directory_granted_is_the_repo_because_the_diff_is_no_longer_a_file_somewhere(
        self, argv: Argv
    ) -> None:
        assert argv.values_of("--add-dir") == [SliceUnderReviewMother.WORKTREE, str(JudgeMother.YARDSTICK)]

    def test_the_mcp_servers_are_bounded(self, argv: Argv) -> None:
        assert argv.contains("--strict-mcp-config")

    def test_only_user_settings_load_so_the_destination_repo_does_not_pay_its_own_claude_md(self, argv: Argv) -> None:
        assert argv.value_of("--setting-sources") == "user"

    def test_the_streamed_envelope_of_the_harness_is_asked_for_so_its_turns_can_be_watched_as_they_happen(
        self, argv: Argv
    ) -> None:
        assert argv.value_of("--output-format") == "stream-json"
        assert argv.contains("--verbose")

    def test_the_schema_that_travels_is_the_one_the_payload_generates_and_not_another(self, argv: Argv) -> None:
        assert json.loads(argv.value_of("--json-schema")) == VerdictPayload.json_schema()

    def test_no_value_follows_another_value_because_each_hangs_from_its_own_flag(self, argv: Argv) -> None:
        assert argv.executable == "claude"
        assert argv.values_that_follow_another_value() == []


class TestWhatTravelsOnStandardInput:
    @staticmethod
    def _block(text: str, tag: str) -> re.Match[str]:
        match = re.search(rf'<{tag} id="([0-9a-f]{{8}})">\n(.*)\n</{tag} id="\1">', text, re.DOTALL)
        assert match, f"no <{tag}> block closed with its own id"

        return match

    def test_the_data_come_first_and_the_rubric_closes_the_text_so_the_long_context_precedes_the_instructions(
        self,
    ) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert text.startswith("<datos_del_run")
        assert text.index("<datos_del_run") < text.index("<diff") < text.index(_JUDGE.rubric)
        assert text.endswith(_JUDGE.rubric)

    def test_the_design_rubric_follows_the_general_one_right_after_it_and_closes_the_text(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(designs=(DesignMother.board(),))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert text.endswith(f"{_JUDGE.rubric}\n{SliceVerifierJudge.DESIGN_RUBRIC}")

    def test_the_run_data_travel_in_a_tag_whose_id_is_the_first_eight_hex_digits_of_the_sha256_of_its_content(
        self,
    ) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        block = self._block(JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text, "datos_del_run")

        assert block.group(1) == hashlib.sha256(block.group(2).encode()).hexdigest()[:8]
        assert "- slice: slice-05" in block.group(2)

    def test_the_diff_travels_in_a_tag_whose_id_is_the_first_eight_hex_digits_of_the_sha256_of_its_content(
        self,
    ) -> None:
        review = SliceUnderReviewMother.of_the_slice(text="-    return 1\n+    return 2\n")

        block = self._block(JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text, "diff")

        assert block.group(2) == review.diff.text
        assert block.group(1) == hashlib.sha256(review.diff.text.encode()).hexdigest()[:8]

    def test_a_diff_that_contains_a_closing_tag_and_a_heading_keeps_both_before_the_closing_with_its_id(self) -> None:
        diff_text = "+# titulo\n+## Datos del run\n+</diff>\n+## otro encabezado\n"
        review = SliceUnderReviewMother.of_the_slice(text=diff_text)

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        closing = f'</diff id="{hashlib.sha256(diff_text.encode()).hexdigest()[:8]}">'
        assert text.index("+</diff>") < text.index(closing)
        assert text.index("+## otro encabezado") < text.index(closing)
        assert text.count(closing) == 1

    def test_the_headings_that_opened_the_blocks_no_longer_exist(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "## Datos del run" not in text
        assert "## Diff de la slice" not in text

    def test_it_carries_the_worktree_the_judge_still_has_to_read_around_the_diff(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()

        assert review.worktree in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

    def test_the_diff_itself_travels_so_a_verdict_cannot_be_reached_without_having_been_shown_it(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(text="-    return 1\n+    return 2\n")

        assert "+    return 2" in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

    def test_it_carries_the_scope_so_it_does_not_depend_on_the_judge_reading_the_diff_the_same_way(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py", "src/tests/test_a.py"))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "src/a.py" in text
        assert "src/tests/test_a.py" in text
        assert "(2)" in text

    def test_it_carries_the_slice_it_judges_with_the_yardstick_the_closed_rubric_measures_it_against(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py",))

        assert (
            "- slice: slice-05\n"
            "- repo: alcaptar/slice-runner\n"
            "- ruta del repo: /repos/project\n"
            "- senal: exenta - este repo no despliega\n"
            "- excluye: \n"
            "- sustituye: \n"
            "- criterios de aceptacion (2):\n"
            "  - antes de tocar codigo comprueba que la subissue no este ya cerrada\n"
            "  - cada precheck falla con un motivo distinguible, no con un booleano\n"
            "- fuentes de convencion (1):\n"
            "  - doc: CLAUDE.md\n"
            "    reglas del repo\n"
            "- checklist de slices del issue (2):\n"
            "  - [CLOSED] slice-05 (prechecks-deterministas): comprobar antes de tocar codigo\n"
            "  - [OPEN] slice-06 (pausa-de-alineacion): el entendimiento se escribe siempre\n"
            "- ficheros que toca la slice (1):\n"
            "  - src/a.py\n"
            "- directorios que puedes leer (2):\n"
            "  - /repos/project\n"
            "  - /toolbox/skills\n"
            "- hallazgos de la ronda anterior (0):\n"
        ) in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

    def test_a_slice_that_declared_something_excluded_carries_it_in_the_excluye_line(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(excludes="el panel de grafana que consume esta serie")

        assert (
            "- excluye: el panel de grafana que consume esta serie\n"
            in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text
        )

    def test_a_slice_that_declared_something_it_replaces_carries_it_in_the_sustituye_line(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(replaces="si - el adaptador viejo; apagando el flag")

        assert (
            "- sustituye: si - el adaptador viejo; apagando el flag\n"
            in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text
        )

    def test_a_slice_with_a_user_story_names_the_slice_by_its_canonical_identifier_not_the_bare_ordinal(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(slice_id=SliceUnderReviewMother.SLICE_ID_WITH_A_USER_STORY)

        assert "- slice: PROJ-1234-05\n" in JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

    def test_what_the_judge_may_read_is_labelled_apart_from_the_files_of_the_slice(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(files=("src/a.py",))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert text.index("src/a.py") < text.index("directorios que puedes leer")
        assert text.index("directorios que puedes leer") < text.index(str(JudgeMother.YARDSTICK))

    def test_a_prior_finding_with_a_line_is_cited_with_its_severity_rule_path_line_evidence_and_detail(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(prior_findings=(FindingMother.with_line(line=42),))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert (
            "- hallazgos de la ronda anterior (1):\n"
            "  - `f1` [medium] convenciones en src/x.py:42: prose in a `.py` (detalle: the why lives in the "
            "pull request body)\n"
        ) in text

    def test_a_prior_finding_with_no_line_is_cited_with_the_path_alone(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(prior_findings=(FindingMother.without_line(),))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert (
            "- hallazgos de la ronda anterior (1):\n"
            "  - `f1` [high] cobertura-capa en src/x.py: the acceptance criterion has no test (detalle: the test "
            "that accredits it is missing)\n"
        ) in text

    def test_two_prior_findings_get_distinguishable_identifiers_so_the_judge_can_cite_them_apart(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(
            prior_findings=(FindingMother.with_line(line=42), FindingMother.without_line())
        )

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "`f1` [medium]" in text
        assert "`f2` [high]" in text

    def test_a_prior_finding_with_a_very_long_detail_carries_it_whole_without_being_truncated(self) -> None:
        finding = FindingMother.with_a_very_long_detail()
        review = SliceUnderReviewMother.of_the_slice(prior_findings=(finding,))

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert finding.detail in text

    def test_two_declared_gaps_are_distinguishable_entries_in_the_prompt(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(debt=SliceUnderReviewMother.two_declared_gaps())

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert (
            "- lo que el implementador declaro dejar fuera (2):\n"
            "  - el cableado del subcomando queda para otra slice\n"
            "  - la migracion de datos historicos\n"
        ) in text

    def test_no_declared_gaps_is_distinguishable_from_a_missing_input_by_the_zero_count(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(debt=())

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "- lo que el implementador declaro dejar fuera (0):\n" in text

    def test_a_decision_of_the_parent_and_one_of_the_subissue_both_reach_the_judge_in_that_order(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(
            decisions=SliceUnderReviewMother.one_decision_of_the_parent_and_one_of_the_subissue()
        )

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert (
            "- decisiones de diseno (2):\n"
            "  - el padre decide el reparto de responsabilidades entre las capas\n"
            "  - la subissue decide que el campo se llama deviations\n"
        ) in text

    def test_no_decisions_is_distinguishable_from_a_missing_input_by_the_zero_count(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(decisions=())

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "- decisiones de diseno (0):\n" in text

    def test_two_declared_deviations_are_distinguishable_entries_in_the_prompt(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(deviations=SliceUnderReviewMother.two_declared_deviations())

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert (
            "- decisiones de diseno que el implementador declaro no seguir (2):\n"
            "  - el puerto no admite la firma decidida porque ya la consume otro adaptador\n"
            "  - la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza\n"
        ) in text

    def test_no_declared_deviations_is_distinguishable_from_a_missing_input_by_the_zero_count(self) -> None:
        review = SliceUnderReviewMother.of_the_slice(deviations=())

        text = JudgeInvocation(judge=_JUDGE, review=review, reader=_READER).text

        assert "- decisiones de diseno que el implementador declaro no seguir (0):\n" in text

    def test_the_prompt_does_not_also_travel_in_the_argv(self) -> None:
        invocation = JudgeInvocation(
            judge=JudgeMother.reading_the_repo_and_its_yardstick(),
            review=SliceUnderReviewMother.of_the_slice(),
            reader=_READER,
        )

        assert invocation.text not in invocation.argv
