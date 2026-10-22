from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from slice_runner.domain.exceptions import UnreadableEventLogError
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class TestWhatTheProgramEmits:
    _SPEND: ClassVar[dict[str, object]] = {
        "cost_usd": 0.3433209,
        "turns": 9,
        "duration_ms": 36315,
        "calls": 1,
        "models": ["claude-sonnet-5"],
        "input_tokens": 13,
        "output_tokens": 1159,
        "cache_creation_tokens": 42251,
        "cache_read_tokens": 241303,
        "ttft_ms": 5588,
        "duration_api_ms": 32189,
    }
    _ROUNDS: ClassVar[dict[str, object]] = {
        "controls": {"used": 0, "limit": 2},
        "hygiene": {"used": 0, "limit": 2},
        "judge": {"used": 0, "limit": 2},
        "ci": {"used": 0, "limit": 1},
        "ci_indeterminate": {"used": 0, "limit": 10},
        "catch_up": {"used": 0, "limit": 3},
    }

    def test_the_event_serialises_with_the_coordinates_the_standing_the_step_the_rounds_the_spend_and_the_budget(
        self,
    ) -> None:
        assert EventPayload.from_domain(EventMother.advancing()).to_contract() == {
            "slice_id": "slice-05",
            "repo": EventMother.REPO,
            "issue": EventMother.ISSUE,
            "ts": "2024-01-01T12:30:45+00:00",
            "standing": "in-progress",
            "step": "run-controls",
            "rounds": self._ROUNDS,
            "spend": self._SPEND,
            "budget_usd": 50.0,
            "parent": FeatureSliceMother.PARENT,
            "name": FeatureSliceMother.NAME,
        }

    def test_an_event_with_a_pull_request_and_a_pid_writes_both_and_reads_them_back(self) -> None:
        event = EventMother.awaiting_merge_of_a_pull_request_from_a_process()

        contract = EventPayload.from_domain(event).to_contract()

        assert (contract["pull_request"], contract["pid"]) == (EventMother.PULL_REQUEST, EventMother.PID)
        assert EventPayload.from_dict(contract).to_domain() == event

    def test_an_event_without_a_pull_request_or_a_pid_leaves_both_keys_out(self) -> None:
        contract = EventPayload.from_domain(EventMother.pending()).to_contract()

        assert {"pull_request", "pid"} & set(contract) == set()

    def test_an_event_with_a_comparison_page_writes_its_path_and_reads_it_back(self) -> None:
        event = EventMother.awaiting_merge_with_a_comparison_page()

        contract = EventPayload.from_domain(event).to_contract()

        assert contract["comparison"] == EventMother.COMPARISON
        assert EventPayload.from_dict(contract).to_domain() == event

    def test_an_event_without_a_comparison_page_leaves_the_key_out(self) -> None:
        contract = EventPayload.from_domain(EventMother.awaiting_merge()).to_contract()

        assert "comparison" not in contract

    def test_a_row_written_before_the_comparison_existed_is_still_read(self) -> None:
        row = EventPayload.from_domain(EventMother.awaiting_merge_of_a_pull_request_from_a_process()).to_contract()

        assert "comparison" not in row
        assert EventPayload.from_dict(row).to_domain().comparison is None

    def test_an_event_never_writes_a_status_key(self) -> None:
        events = (EventMother.advancing(), EventMother.pending(), EventMother.closed())

        assert all("status" not in EventPayload.from_domain(event).to_contract() for event in events)

    def test_a_closing_event_writes_the_standing_and_the_reason_it_closed_with(self) -> None:
        merged = EventPayload.from_domain(EventMother.closed()).to_contract()
        blocked = EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract()

        assert (merged["standing"], "reason" in merged) == ("merged", False)
        assert (blocked["standing"], blocked["reason"]) == ("blocked", "judge")

    def test_a_pending_event_writes_the_pending_standing_and_leaves_the_step_out(self) -> None:
        row = EventPayload.from_domain(EventMother.pending()).to_contract()

        assert row["standing"] == "pending"
        assert "step" not in row

    def test_a_round_without_changes_writes_the_flag_as_true_and_any_other_event_leaves_it_out(self) -> None:
        flagged = EventPayload.from_domain(EventMother.round_without_changes()).to_contract()
        plain = EventPayload.from_domain(EventMother.advancing()).to_contract()

        assert flagged["round_without_changes"] is True
        assert "round_without_changes" not in plain


class TestWhatTheProgramReads:
    @pytest.mark.parametrize(
        "event",
        [
            EventMother.advancing(),
            EventMother.pending(),
            EventMother.closed(),
            EventMother.blocked_by_the_judge(),
            EventMother.awaiting_merge(),
            EventMother.round_without_changes(),
            EventMother.advancing_before_the_feature_was_recorded(),
        ],
    )
    def test_a_row_reads_back_as_the_event_that_was_written(self, event: Event) -> None:
        row = EventPayload.from_domain(event).to_contract()

        assert EventPayload.from_dict(row).to_domain() == event

    def test_an_event_without_the_feature_writes_neither_key(self) -> None:
        row = EventPayload.from_domain(EventMother.advancing_before_the_feature_was_recorded()).to_contract()

        assert "parent" not in row
        assert "name" not in row

    def test_a_row_with_a_status_field_is_refused(self) -> None:
        row = {**EventPayload.from_domain(EventMother.advancing()).to_contract(), "status": "advancing"}

        with pytest.raises(UnreadableEventLogError, match="status"):
            EventPayload.from_dict(row)

    def test_a_row_of_the_previous_generation_with_closed_as_is_refused(self) -> None:
        row = {**EventPayload.from_domain(EventMother.closed()).to_contract(), "closed_as": "merged"}

        with pytest.raises(UnreadableEventLogError, match="closed_as"):
            EventPayload.from_dict(row)

    def test_a_blocked_standing_without_a_reason_is_refused(self) -> None:
        row = {**EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract()}
        del row["reason"]

        with pytest.raises(UnreadableEventLogError, match="standing"):
            EventPayload.from_dict(row)

    def test_a_reason_that_belongs_to_another_standing_is_refused(self) -> None:
        row = {**EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract(), "reason": "budget"}

        with pytest.raises(UnreadableEventLogError, match="standing"):
            EventPayload.from_dict(row)

    def test_a_pending_standing_with_a_step_is_refused(self) -> None:
        row = {**EventPayload.from_domain(EventMother.pending()).to_contract(), "step": "implement"}

        with pytest.raises(UnreadableEventLogError, match="standing"):
            EventPayload.from_dict(row)
