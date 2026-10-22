from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.register_pending_slices import (
    RegisterPendingSlices,
    RegisterPendingSlicesParams,
)
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.child_issues import ChildIssues
from slice_runner.domain.clock import Clock
from slice_runner.domain.closure import Closure
from slice_runner.domain.event import Event
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.event_reader import EventBatch, EventReader
from slice_runner.domain.exceptions import UnreadableEventLogError
from slice_runner.domain.feature_slice import FeatureSlice
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.rounds import Rounds
from slice_runner.tests.mothers.child_issue_mother import ChildIssueMother
from slice_runner.tests.mothers.event_mother import EventMother


class TestRegisteringThePendingSlices:
    _NOW = datetime(2026, 10, 8, 9, 0, 0, tzinfo=UTC)
    _PARAMS = RegisterPendingSlicesParams(repo=ChildIssueMother.REPO, parent=ChildIssueMother.PARENT)

    @staticmethod
    def _children(*children: object) -> Mock:
        port: Mock = create_autospec(ChildIssues, spec_set=True, instance=True)
        port.of_parent.return_value = tuple(children)

        return port

    @staticmethod
    def _reader(*events: Event) -> Mock:
        reader: Mock = create_autospec(EventReader, spec_set=True, instance=True)
        reader.read_since.return_value = EventBatch(events=events, cursor=EventCursor(offset=10))

        return reader

    @classmethod
    def _action(cls, *, children: Mock, reader: Mock, log: Mock) -> RegisterPendingSlices:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = cls._NOW

        return RegisterPendingSlices(children=children, reader=reader, log=log, clock=clock, budgets=Budgets())

    @staticmethod
    def _log() -> Mock:
        log: Mock = create_autospec(EventLog, spec_set=True, instance=True)

        return log

    @staticmethod
    def _emitted(log: Mock) -> list[Event]:
        return [call.args[0] for call in log.emit.call_args_list]

    def test_of_four_subissues_it_writes_one_event_for_each_open_one_without_events_and_none_for_the_rest(
        self,
    ) -> None:
        already_started = replace(EventMother.advancing(), repo=ChildIssueMother.REPO, issue=526, slice_id="slice-03")
        children = self._children(
            ChildIssueMother.open(number=524, ordinal=1),
            ChildIssueMother.closed(number=525, ordinal=2),
            ChildIssueMother.open(number=526, ordinal=3),
            ChildIssueMother.open(number=527, ordinal=4),
        )
        log = self._log()

        result = self._action(children=children, reader=self._reader(already_started), log=log).execute(self._PARAMS)

        assert [event.issue for event in self._emitted(log)] == [524, 527]
        assert result.registered == tuple(self._emitted(log))

    def test_a_pending_event_is_open_with_zero_spend_and_no_step_and_carries_its_parent_and_name(self) -> None:
        log = self._log()

        self._action(
            children=self._children(ChildIssueMother.open(number=524, ordinal=1, name="registrar")),
            reader=self._reader(),
            log=log,
        ).execute(self._PARAMS)

        assert self._emitted(log) == [
            Event(
                slice_id="slice-01",
                repo=ChildIssueMother.REPO,
                issue=524,
                step=None,
                at=self._NOW,
                spend=HarnessSpend.nothing(),
                budget_usd=Budgets().slice_cost_usd,
                rounds=Rounds.untouched(Budgets()),
                closure=Closure.open(),
                feature_slice=FeatureSlice(parent=ChildIssueMother.PARENT, name="registrar"),
            )
        ]

    def test_the_slice_id_of_a_pending_event_is_the_canonical_one_of_a_slice_with_a_user_story(self) -> None:
        log = self._log()

        self._action(
            children=self._children(ChildIssueMother.open_of_a_user_story()), reader=self._reader(), log=log
        ).execute(self._PARAMS)

        assert [event.slice_id for event in self._emitted(log)] == ["HU-123-01"]

    def test_the_same_issue_number_in_another_repo_does_not_count_as_already_started(self) -> None:
        elsewhere = replace(EventMother.advancing_in_another_repo(), issue=524, slice_id="slice-01")
        log = self._log()

        self._action(
            children=self._children(ChildIssueMother.open(number=524, ordinal=1)),
            reader=self._reader(elsewhere),
            log=log,
        ).execute(self._PARAMS)

        assert [event.issue for event in self._emitted(log)] == [524]

    def test_an_unreadable_log_writes_nothing_and_does_not_ask_github_for_the_subissues(self) -> None:
        reader: Mock = create_autospec(EventReader, spec_set=True, instance=True)
        reader.read_since.side_effect = UnreadableEventLogError("not JSON")
        children = self._children(ChildIssueMother.open())
        log = self._log()

        with pytest.raises(UnreadableEventLogError):
            self._action(children=children, reader=reader, log=log).execute(self._PARAMS)

        log.emit.assert_not_called()
        children.of_parent.assert_not_called()

    def test_it_asks_for_the_subissues_of_the_given_parent_in_the_given_repo(self) -> None:
        children = self._children()

        self._action(children=children, reader=self._reader(), log=self._log()).execute(self._PARAMS)

        children.of_parent.assert_called_once_with(repo=ChildIssueMother.REPO, parent=ChildIssueMother.PARENT)
