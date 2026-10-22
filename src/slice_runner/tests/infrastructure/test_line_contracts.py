from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.slice_status import SliceStatus
from slice_runner.infrastructure.follow_transition_v2_payload import FollowTransitionV2Payload
from slice_runner.infrastructure.slice_status_line_payload import SliceStatusLinePayload
from slice_runner.tests.mothers.closed_slice_record_mother import ClosedSliceRecordMother
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother


class TheLineAgainstItsExamples:
    _CONTRACT: ClassVar[Path]

    @classmethod
    def _declared(cls) -> dict[str, object]:
        declared: dict[str, object] = json.loads(cls._CONTRACT.read_text(encoding="utf-8"))

        return declared

    @classmethod
    def _keys_of_the_examples(cls) -> set[str]:
        examples = cls._declared()["examples"]
        assert isinstance(examples, list)

        return {key for example in examples for key in example}

    @classmethod
    def _required(cls) -> set[str]:
        optional = cls._declared()["optional"]
        assert isinstance(optional, list)

        return cls._keys_of_the_examples() - set(optional)

    @staticmethod
    def _emitted() -> list[dict[str, object]]:
        raise NotImplementedError

    def test_the_program_never_emits_a_key_the_examples_do_not_have(self) -> None:
        emitted = {key for line in self._emitted() for key in line}

        assert emitted - self._keys_of_the_examples() == set()

    def test_the_program_always_emits_the_keys_the_examples_do_not_mark_as_optional(self) -> None:
        for line in self._emitted():
            assert self._required() - set(line) == set()

    def test_the_optional_keys_are_all_keys_the_examples_carry(self) -> None:
        optional = self._declared()["optional"]
        assert isinstance(optional, list)

        assert set(optional) <= self._keys_of_the_examples()

    def test_the_optional_keys_are_the_ones_the_program_leaves_out_when_it_has_no_value(self) -> None:
        optional = self._declared()["optional"]
        assert isinstance(optional, list)
        left_out = {key for key in self._keys_of_the_examples() for line in self._emitted() if key not in line}

        assert left_out == set(optional)


class TestTheFollowTransitionLineAgainstItsExamples:
    _CONTRACT: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "follow-line-v2.json"

    @classmethod
    def _examples_of_the_transition(cls) -> list[dict[str, object]]:
        declared = json.loads(cls._CONTRACT.read_text(encoding="utf-8"))

        return [example for example in declared["examples"] if example["kind"] == "transition"]

    @staticmethod
    def _emitted() -> list[dict[str, object]]:
        events = (
            EventMother.advancing(),
            EventMother.closed(),
            EventMother.blocked_by_the_judge(),
            EventMother.round_without_changes(),
            EventMother.advancing_before_the_feature_was_recorded(),
            EventMother.pending(),
            EventMother.awaiting_merge_with_a_comparison_page(),
        )

        return [FollowTransitionV2Payload.from_domain(event).to_contract() for event in events]

    def test_every_emitted_line_validates_against_the_transition_model(self) -> None:
        for line in self._emitted():
            FollowTransitionV2Payload.from_contract(line)

    def test_the_program_never_emits_a_key_the_examples_of_the_transition_do_not_have(self) -> None:
        declared = {key for example in self._examples_of_the_transition() for key in example}
        emitted = {key for line in self._emitted() for key in line}

        assert emitted - declared == set()

    @staticmethod
    def _without_the_instant_and_the_limits(line: dict[str, object]) -> dict[str, object]:
        rounds = line["rounds"]
        assert isinstance(rounds, dict)
        used = {name: counter["used"] for name, counter in rounds.items()}

        return {**{key: value for key, value in line.items() if key not in ("ts", "rounds")}, "rounds": used}

    def test_the_line_of_a_pending_event_equals_its_example_value_by_value_except_the_instant_and_the_limits(
        self,
    ) -> None:
        example = next(example for example in self._examples_of_the_transition() if example["standing"] == "pending")
        line = FollowTransitionV2Payload.from_domain(EventMother.pending()).to_contract()

        assert self._without_the_instant_and_the_limits(line) == self._without_the_instant_and_the_limits(example)


class TestTheStatusLineAgainstItsExamples(TheLineAgainstItsExamples):
    _CONTRACT: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "status-line.json"

    @staticmethod
    def _emitted() -> list[dict[str, object]]:
        spend = HarnessSpendMother.of_the_judge_call()
        statuses = (
            SliceStatus(
                sub_issue=SubIssueMother.blocked(IssueLabel.IN_PROGRESS, RunMother.judging_after_spending(spend)),
                pull_request=47,
                spend=spend,
            ),
            SliceStatus(sub_issue=SubIssueMother.unlabelled(), pull_request=None),
            SliceStatus(sub_issue=SubIssueMother.closed(), pull_request=None, record=ClosedSliceRecordMother.merged()),
        )

        return [SliceStatusLinePayload.from_domain(status).to_contract() for status in statuses]
