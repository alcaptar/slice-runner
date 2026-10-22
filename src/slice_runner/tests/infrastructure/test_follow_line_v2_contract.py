from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from slice_runner.domain.exceptions import UnreadableFollowLineError
from slice_runner.infrastructure.follow_activity_v2_payload import FollowActivityV2Payload
from slice_runner.infrastructure.follow_actor import FollowActor
from slice_runner.infrastructure.follow_reason import FollowReason
from slice_runner.infrastructure.follow_standing import FollowStanding
from slice_runner.infrastructure.follow_transition_v2_payload import FollowTransitionV2Payload
from slice_runner.tests.mothers.event_mother import EventMother


class TheV2Contract:
    _CONTRACT: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "follow-line-v2.json"

    @classmethod
    def _examples(cls) -> list[dict[str, object]]:
        declared = json.loads(cls._CONTRACT.read_text(encoding="utf-8"))
        examples: list[dict[str, object]] = declared["examples"]

        return examples

    @classmethod
    def _example_of_the_standing(cls, standing: str, reason: str | None = None) -> dict[str, object]:
        return next(
            dict(example)
            for example in cls._examples()
            if example.get("standing") == standing and example.get("reason") == reason
        )

    @classmethod
    def _example_of_the_activity(cls) -> dict[str, object]:
        return next(dict(example) for example in cls._examples() if example["kind"] == "activity")


class TestEveryExampleOfTheContractIsValid(TheV2Contract):
    def test_the_model_of_its_kind_accepts_every_example_and_gives_it_back_unchanged(self) -> None:
        for example in self._examples():
            model = FollowTransitionV2Payload if example["kind"] == "transition" else FollowActivityV2Payload

            assert model.from_contract(example).to_contract() == example

    def test_the_examples_carry_every_standing(self) -> None:
        carried = {example["standing"] for example in self._examples() if example["kind"] == "transition"}

        assert carried == {str(standing) for standing in FollowStanding}

    def test_the_examples_carry_every_reason(self) -> None:
        carried = {example["reason"] for example in self._examples() if "reason" in example}

        assert carried == {str(reason) for reason in FollowReason}

    def test_the_examples_carry_every_actor(self) -> None:
        carried = {example["actor"] for example in self._examples() if example["kind"] == "activity"}

        assert carried == {str(actor) for actor in FollowActor}

    def test_the_optional_keys_the_contract_declares_are_the_ones_some_example_leaves_out(self) -> None:
        declared = json.loads(self._CONTRACT.read_text(encoding="utf-8"))["optional"]
        transitions = [example for example in self._examples() if example["kind"] == "transition"]
        left_out = {key for example in transitions for key in set(declared) if key not in example}

        assert left_out == set(declared)


class TestTheModelRejectsWhatTheContractForbids(TheV2Contract):
    def test_a_pending_line_with_a_reason_is_rejected(self) -> None:
        line = self._example_of_the_standing("pending") | {"reason": "controls"}

        with pytest.raises(UnreadableFollowLineError, match="reason"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_blocked_line_without_a_reason_is_rejected(self) -> None:
        line = self._example_of_the_standing("blocked", "controls")
        del line["reason"]

        with pytest.raises(UnreadableFollowLineError, match="reason"):
            FollowTransitionV2Payload.from_contract(line)

    def test_an_aborted_line_with_a_blocking_reason_is_rejected(self) -> None:
        line = self._example_of_the_standing("aborted", "budget") | {"reason": "ci-red"}

        with pytest.raises(UnreadableFollowLineError, match="reason"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_blocked_line_with_an_aborting_reason_is_rejected(self) -> None:
        line = self._example_of_the_standing("blocked", "controls") | {"reason": "budget"}

        with pytest.raises(UnreadableFollowLineError, match="reason"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_line_that_is_neither_blocked_nor_aborted_with_a_reason_is_rejected(self) -> None:
        line = self._example_of_the_standing("in-progress") | {"reason": "judge"}

        with pytest.raises(UnreadableFollowLineError, match="reason"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_pending_line_with_a_step_is_rejected(self) -> None:
        line = self._example_of_the_standing("pending") | {"step": "implement"}

        with pytest.raises(UnreadableFollowLineError, match="step"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_line_that_is_not_pending_without_a_step_is_rejected(self) -> None:
        line = self._example_of_the_standing("in-progress")
        del line["step"]

        with pytest.raises(UnreadableFollowLineError, match="step"):
            FollowTransitionV2Payload.from_contract(line)

    def test_a_key_the_contract_does_not_know_is_rejected(self) -> None:
        line = self._example_of_the_activity() | {"summary": "editing"}

        with pytest.raises(UnreadableFollowLineError, match="summary"):
            FollowActivityV2Payload.from_contract(line)


class TestTheTransitionBuiltFromAnEvent:
    def test_it_carries_the_pull_request_and_the_pid_of_the_event(self) -> None:
        line = FollowTransitionV2Payload.from_domain(EventMother.awaiting_merge_of_a_pull_request_from_a_process())

        assert (line.pull_request, line.pid) == (EventMother.PULL_REQUEST, EventMother.PID)

    def test_it_carries_the_comparison_page_of_the_event(self) -> None:
        line = FollowTransitionV2Payload.from_domain(EventMother.awaiting_merge_with_a_comparison_page())

        assert line.to_contract()["comparison"] == EventMother.COMPARISON

    def test_an_event_without_a_page_leaves_the_comparison_key_out_of_the_line(self) -> None:
        contract = FollowTransitionV2Payload.from_domain(EventMother.awaiting_merge()).to_contract()

        assert "comparison" not in contract

    def test_an_event_without_them_leaves_both_keys_out_of_the_line(self) -> None:
        contract = FollowTransitionV2Payload.from_domain(EventMother.pending()).to_contract()

        assert {"pull_request", "pid"} & set(contract) == set()
