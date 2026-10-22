from __future__ import annotations

from slice_runner.infrastructure.slice_verifier_judge import SliceVerifierJudge


class TestWhatTheRubricSaysAboutDesignDecisions:
    @staticmethod
    def _said() -> str:
        return " ".join(SliceVerifierJudge.adversarial().rubric.split())

    def test_it_fails_a_diff_that_departs_from_a_decision_the_implementer_did_not_declare(self) -> None:
        assert (
            "Un diff que se aparta de una decision de diseno sin que el implementador la haya declarado en "
            "`deviations` es un hallazgo de **severity high**"
        ) in self._said()

    def test_it_lets_a_declared_deviation_through_without_blocking(self) -> None:
        assert "Una desviacion declarada **no bloquea**" in self._said()

    def test_it_names_the_rule_a_decision_finding_is_reported_under(self) -> None:
        assert "`decisiones`" in self._said()

    def test_it_lists_both_inputs_among_what_the_prompt_carries(self) -> None:
        assert "**Las decisiones de diseno**" in self._said()
        assert "**Las desviaciones que el implementador declaro**" in self._said()
