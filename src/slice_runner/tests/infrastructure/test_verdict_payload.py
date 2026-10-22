from __future__ import annotations

import json
from dataclasses import fields

import pytest

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.finding import Finding
from slice_runner.domain.prior_finding_ruling import PriorFindingState
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.verdict_payload import FindingPayload, VerdictPayload
from slice_runner.tests.mothers.judge_output_mother import JudgeVerdictMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, PriorFindingRulingMother, VerdictMother


class TestTheContractVocabulary:
    def test_every_field_of_a_finding_has_a_payload_field_so_that_none_is_dropped_on_the_way_out(self) -> None:
        assert {declared.name for declared in fields(Finding)} == set(FindingPayload.model_fields)

    def test_no_boundary_field_declares_an_alias_because_the_contract_key_is_the_field_name(self) -> None:
        declared = [*FindingPayload.model_fields.values(), *VerdictPayload.model_fields.values()]

        assert all(field.alias is None for field in declared)


class TestWhatTheProgramEmits:
    def test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null(self) -> None:
        emitted = FindingPayload.from_domain(FindingMother.without_line()).to_contract()

        assert "line" not in emitted

    def test_a_finding_with_a_line_emits_it_as_an_integer_not_as_text(self) -> None:
        emitted = FindingPayload.from_domain(FindingMother.with_line(42)).to_contract()

        assert emitted["line"] == 42

    def test_the_verdict_serialises_with_the_contract_vocabulary_not_with_the_domain_names(self) -> None:
        verdict = VerdictMother.failing(FindingMother.without_line())

        assert VerdictPayload.from_domain(verdict).to_contract() == {
            "ruling": "FAIL",
            "findings": [
                {
                    "rule": "cobertura-capa",
                    "path": "src/x.py",
                    "severity": "high",
                    "evidence": "the acceptance criterion has no test",
                    "detail": "the test that accredits it is missing",
                }
            ],
            "prior_rulings": [],
        }

    def test_a_verdict_survives_the_round_trip_through_the_contract_without_losing_a_field(self) -> None:
        verdict = VerdictMother.failing(FindingMother.with_line(11), FindingMother.without_line())

        assert VerdictPayload.from_domain(verdict).to_domain() == verdict

    def test_a_pronouncement_on_a_prior_finding_survives_the_round_trip_through_the_contract(self) -> None:
        verdict = VerdictMother.pronouncing_on(PriorFindingRulingMother.retired())

        assert VerdictPayload.from_domain(verdict).to_domain() == verdict


class TestTheSchemaTheJudgeReceives:
    def test_it_declares_every_finding_field_of_the_domain_under_its_contract_key(self) -> None:
        assert set(self._at("properties", "findings", "items", "properties")) == FindingPayload.contract_keys()

    def test_it_requires_every_finding_field_but_the_line(self) -> None:
        required = self._at("properties", "findings", "items")["required"]

        assert isinstance(required, list)
        assert set(required) == FindingPayload.contract_keys() - {"line"}

    def test_it_closes_both_objects_so_the_judge_is_told_not_to_invent_keys(self) -> None:
        assert VerdictPayload.json_schema()["additionalProperties"] is False
        assert self._at("properties", "findings", "items")["additionalProperties"] is False

    def test_it_spells_the_verdicts_out_as_an_enum(self) -> None:
        assert self._at("properties", "ruling")["enum"] == [str(ruling) for ruling in Ruling]

    def test_it_spells_the_severities_out_as_an_enum(self) -> None:
        severity = self._at("properties", "findings", "items", "properties", "severity")

        assert severity["enum"] == [str(severity) for severity in Severity]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(VerdictPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    def test_it_declares_the_pronouncement_on_a_prior_finding_as_optional_since_the_first_round_has_none(
        self,
    ) -> None:
        required = VerdictPayload.json_schema()["required"]

        assert isinstance(required, list)
        assert "prior_rulings" not in required

    def test_it_requires_the_id_and_the_state_of_a_pronouncement_but_not_the_reason(self) -> None:
        required = self._at("properties", "prior_rulings", "items")["required"]

        assert isinstance(required, list)
        assert set(required) == {"id", "state"}

    def test_it_spells_the_pronouncement_states_out_as_an_enum(self) -> None:
        state = self._at("properties", "prior_rulings", "items", "properties", "state")

        assert state["enum"] == [str(member) for member in PriorFindingState]

    @staticmethod
    def _at(*path: str) -> dict[str, object]:
        node: object = VerdictPayload.json_schema()
        for key in path:
            assert isinstance(node, dict)
            node = node[key]
        assert isinstance(node, dict)

        return node


class TestThePronouncementOnPriorFindings:
    def test_a_pronouncement_with_no_reason_validates_because_only_retiring_one_requires_a_reason(self) -> None:
        pronouncing = JudgeVerdictMother.passing() | {"prior_rulings": [{"id": "f1", "state": "corregido"}]}

        payload = VerdictPayload.from_dict(pronouncing)

        assert payload.to_domain().prior_rulings == (PriorFindingRulingMother.fixed(),)

    def test_a_retired_pronouncement_carries_the_reason_it_was_retired_for(self) -> None:
        reason = "el criterio que citaba ya no existe"
        pronouncing = JudgeVerdictMother.passing() | {
            "prior_rulings": [{"id": "f1", "state": "retirado", "reason": reason}]
        }

        payload = VerdictPayload.from_dict(pronouncing)

        assert payload.to_domain().prior_rulings == (PriorFindingRulingMother.retired(reason=reason),)

    def test_a_verdict_dict_written_before_this_slice_without_prior_rulings_is_still_read(self) -> None:
        payload = VerdictPayload.from_dict(JudgeVerdictMother.passing())

        assert payload.to_domain().prior_rulings == ()

    def test_a_pronouncement_naming_a_state_outside_the_vocabulary_is_rejected_saying_which_one_it_was(self) -> None:
        pronouncing = JudgeVerdictMother.passing() | {"prior_rulings": [{"id": "f1", "state": "descartado"}]}

        with pytest.raises(InvalidVerdictError, match="'descartado'"):
            VerdictPayload.from_dict(pronouncing)


class TestWhatTheJudgeIsAllowedToReturn:
    def test_a_verdict_with_no_findings_passes(self) -> None:
        payload = VerdictPayload.from_dict(JudgeVerdictMother.passing())

        assert payload.to_domain() == VerdictMother.passing()

    def test_the_finding_arrives_typed_down_to_its_severity(self) -> None:
        payload = VerdictPayload.from_dict(JudgeVerdictMother.failing())

        assert payload.findings[0].severity is Severity.HIGH

    def test_a_pass_that_comes_with_a_high_severity_finding_is_rejected(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding())

        with pytest.raises(InvalidVerdictError, match="PASS with 1 finding"):
            VerdictPayload.from_dict(incoherent).to_domain()

    def test_a_pass_whose_only_finding_is_medium_severity_is_rejected_like_one_with_a_high(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.medium_severity_finding())

        with pytest.raises(InvalidVerdictError, match="PASS with 1 finding"):
            VerdictPayload.from_dict(incoherent).to_domain()

    def test_a_pass_whose_findings_are_all_low_severity_is_accepted(self) -> None:
        verdict = VerdictPayload.from_dict(
            JudgeVerdictMother.passing_with(
                JudgeVerdictMother.low_severity_finding(), JudgeVerdictMother.low_severity_finding(path="src/y.py")
            )
        ).to_domain()

        assert verdict.ruling is Ruling.PASS

    def test_a_key_we_do_not_know_in_a_finding_is_rejected_instead_of_ignored(self) -> None:
        invented = JudgeVerdictMother.high_severity_finding() | {"campo_nuevo_del_juez": "invented"}

        with pytest.raises(InvalidVerdictError, match="campo_nuevo_del_juez"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(invented))

    def test_a_finding_named_with_the_old_spanish_contract_keys_is_rejected_because_the_contract_is_english(
        self,
    ) -> None:
        in_spanish: dict[str, object] = {"regla": "boundaries", "path": "src/x.py", "severidad": "high"}

        with pytest.raises(InvalidVerdictError, match=r"`findings\.0\.regla` extra inputs are not permitted"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(in_spanish))

    def test_a_severity_outside_the_rubric_is_rejected_saying_which_one_it_was(self) -> None:
        invented = JudgeVerdictMother.high_severity_finding() | {"severity": "critica"}

        with pytest.raises(InvalidVerdictError, match="'critica'"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(invented))

    @pytest.mark.parametrize("line", [True, "11", 1.5])
    def test_a_line_that_is_not_an_integer_is_rejected_instead_of_coerced(self, line: object) -> None:
        with_a_bad_line = JudgeVerdictMother.high_severity_finding() | {"line": line}

        with pytest.raises(InvalidVerdictError, match="line"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(with_a_bad_line))

    def test_a_finding_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete = {
            key: value for key, value in JudgeVerdictMother.high_severity_finding().items() if key != "detail"
        }

        with pytest.raises(InvalidVerdictError, match="detail"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(incomplete))
