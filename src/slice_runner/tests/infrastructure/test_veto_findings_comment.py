from __future__ import annotations

from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.veto_findings_comment import VetoFindingsComment
from slice_runner.tests.mothers.findings_history_mother import FindingsHistoryMother
from slice_runner.tests.mothers.verdict_mother import FindingMother


class TestAllRoundsAreRepresented:
    def test_a_history_with_three_rounds_shows_the_finding_of_every_round(self) -> None:
        history = FindingsHistoryMother.of_three_rounds_with_a_distinct_finding_in_each()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "regla-uno" in rendered
        assert "regla-dos" in rendered
        assert "regla-tres" in rendered


class TestTheLastRoundIsDistinguishedFromEarlierOnes:
    def test_the_finding_from_an_earlier_round_that_did_not_reappear_lands_after_the_one_still_standing(self) -> None:
        history = FindingsHistoryMother.of_a_finding_fixed_by_the_last_round_next_to_one_still_open()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())
        boundary = rendered.index("no reaparecieron")

        assert rendered.index("sigue-abierto") < boundary
        assert rendered.index("ya-corregido") > boundary


class TestGroupingByRuleAndPath:
    def test_the_same_defect_seen_in_three_rounds_with_different_lines_becomes_one_entry_with_three_appearances(
        self,
    ) -> None:
        history = FindingsHistoryMother.of_a_defect_dragged_across_three_rounds_changing_line()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "`f1`" in rendered
        assert "`f2`" not in rendered
        assert "ronda 1 (" in rendered
        assert "ronda 2 (" in rendered
        assert "ronda 3 (" in rendered

    def test_the_same_defect_seen_twice_with_a_different_severity_still_groups_into_one_entry(self) -> None:
        history = FindingsHistoryMother.of_the_same_defect_changing_severity_across_two_rounds()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "`f1`" in rendered
        assert "`f2`" not in rendered
        assert f"ronda 1 ({Severity.HIGH})" in rendered
        assert f"ronda 2 ({Severity.LOW})" in rendered

    def test_two_distinct_evidences_under_the_same_rule_and_path_both_survive_the_grouping(self) -> None:
        first = FindingMother.without_line(evidence="primera evidencia")
        second = FindingMother.without_line(evidence="segunda evidencia")
        history = FindingsHistoryMother.of_two_distinct_defects_under_the_same_rule_and_path()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "`f2`" not in rendered
        assert "primera evidencia" in rendered
        assert "segunda evidencia" in rendered
        assert VetoFindingsComment.finding_of(rendered, "f1") == first
        assert VetoFindingsComment.finding_of(rendered, "f1-1") == second


class TestTheHeaderStatesHowItWasComposed:
    def test_the_number_of_rounds_and_of_entries_after_grouping_both_appear_in_the_body(self) -> None:
        history = FindingsHistoryMother.of_a_defect_dragged_across_three_rounds_changing_line()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "3 ronda" in rendered
        assert "1 hallazgo" in rendered

    def test_the_number_of_rounds_published_is_how_many_are_composed_and_not_the_highest_round_number_seen(
        self,
    ) -> None:
        history = FindingsHistoryMother.of_rounds_four_and_five_with_no_earlier_rounds_archived()

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "2 ronda" in rendered
        assert "5 ronda" not in rendered


class TestASingleRoundKeepsPublishingWhatItDoesToday:
    def test_the_finding_ids_start_at_f1_as_they_did_with_a_plain_tuple_of_findings(self) -> None:
        history = FindingsHistoryMother.of_a_single_round(FindingMother.without_line())

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert "`f1`" in rendered

    def test_the_json_block_still_lets_find_finding_recover_every_finding_by_its_id(self) -> None:
        first = FindingMother.without_line()
        second = FindingMother.low_severity()
        history = FindingsHistoryMother.of_a_single_round(first, second)

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert VetoFindingsComment.finding_of(rendered, "f1") == first
        assert VetoFindingsComment.finding_of(rendered, "f2") == second

    def test_the_marker_and_the_automation_mark_are_both_present(self) -> None:
        history = FindingsHistoryMother.of_a_single_round(FindingMother.without_line())

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt.nothing())

        assert VetoFindingsComment.MARKER in rendered
        assert AutomationMark.TEXT in rendered


class TestWhatTheImplementerDeclaredLeftOut:
    _LEFT_OUT = ("el cableado del subcomando queda para otra slice", "la migracion de datos historicos")

    def test_what_the_implementer_declared_sits_next_to_what_the_judge_still_demands(self) -> None:
        history = FindingsHistoryMother.of_a_single_round(FindingMother.without_line())

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt(declared=True, left_out=self._LEFT_OUT))

        assert "Hallazgos vigentes tras la ultima ronda" in rendered
        assert "Lo que declaro el implementador haber dejado fuera" in rendered
        assert all(f"- {item}" in rendered for item in self._LEFT_OUT)

    def test_a_declaration_that_left_nothing_out_adds_no_section(self) -> None:
        history = FindingsHistoryMother.of_a_single_round(FindingMother.without_line())

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt(declared=True))

        assert "implementador" not in rendered

    def test_the_declaration_does_not_disturb_the_findings_a_later_read_finds_back(self) -> None:
        first = FindingMother.without_line()
        history = FindingsHistoryMother.of_a_single_round(first)

        rendered = VetoFindingsComment.rendered(history, DeclaredDebt(declared=True, left_out=self._LEFT_OUT))

        assert VetoFindingsComment.finding_of(rendered, "f1") == first
