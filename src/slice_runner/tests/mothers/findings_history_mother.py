from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.findings_history import FindingsHistory
from slice_runner.domain.severity import Severity
from slice_runner.tests.mothers.judged_round_mother import JudgedRoundMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class FindingsHistoryMother:
    @staticmethod
    def of_a_single_round(*findings: Finding) -> FindingsHistory:
        return FindingsHistory.of_rounds((JudgedRoundMother.of_the_round(1, *findings),))

    @staticmethod
    def of_three_rounds_with_a_distinct_finding_in_each() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(1, FindingMother.without_line(rule="regla-uno", path="src/a.py")),
                JudgedRoundMother.of_the_round(2, FindingMother.without_line(rule="regla-dos", path="src/b.py")),
                JudgedRoundMother.of_the_round(3, FindingMother.without_line(rule="regla-tres", path="src/c.py")),
            )
        )

    @staticmethod
    def of_a_defect_dragged_across_three_rounds_changing_line() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(1, FindingMother.with_line(1196)),
                JudgedRoundMother.of_the_round(2, FindingMother.with_line(1203)),
                JudgedRoundMother.of_the_round(3, FindingMother.with_line(1715)),
            )
        )

    @staticmethod
    def of_two_distinct_defects_under_the_same_rule_and_path() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(
                    1,
                    FindingMother.without_line(evidence="primera evidencia"),
                    FindingMother.without_line(evidence="segunda evidencia"),
                ),
            )
        )

    @staticmethod
    def of_a_finding_fixed_by_the_last_round_next_to_one_still_open() -> FindingsHistory:
        fixed_already = FindingMother.without_line(rule="ya-corregido", path="src/fixed.py")
        still_open = FindingMother.without_line(rule="sigue-abierto", path="src/open.py")

        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(1, fixed_already, still_open),
                JudgedRoundMother.of_the_round(2, still_open),
            )
        )

    @staticmethod
    def of_the_same_defect_changing_severity_across_two_rounds() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(1, FindingMother.without_line(severity=Severity.HIGH)),
                JudgedRoundMother.of_the_round(2, FindingMother.without_line(severity=Severity.LOW)),
            )
        )

    @staticmethod
    def of_a_high_severity_finding_fixed_before_a_low_severity_one_appears() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(1, FindingMother.without_line()),
                JudgedRoundMother.of_the_round(2, FindingMother.low_severity()),
            )
        )

    @staticmethod
    def of_rounds_four_and_five_with_no_earlier_rounds_archived() -> FindingsHistory:
        return FindingsHistory.of_rounds(
            (
                JudgedRoundMother.of_the_round(4, FindingMother.without_line(rule="regla-cuatro")),
                JudgedRoundMother.of_the_round(5, FindingMother.without_line(rule="regla-cinco")),
            )
        )
