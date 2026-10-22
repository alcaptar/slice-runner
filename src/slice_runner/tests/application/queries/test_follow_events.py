from __future__ import annotations

from datetime import timedelta

import pytest

from slice_runner.application.queries.follow_events import FollowEvents, FollowEventsParams
from slice_runner.domain.closure import Closure
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_reader import EventBatch
from slice_runner.tests.doubles import ScriptedEventReader
from slice_runner.tests.mothers.event_mother import EventMother


class TestWhatTheSnapshotHolds:
    def test_the_snapshot_keeps_the_last_event_of_every_slice_with_its_step_closure_spend_and_instant(self) -> None:
        last = EventMother.closed()
        reader = ScriptedEventReader(EventBatch(events=(EventMother.advancing(), last), cursor=EventCursor(offset=10)))

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert result.snapshot == (last,)
        assert (result.snapshot[0].step, result.snapshot[0].closure) == (last.step, last.closure)
        assert result.snapshot[0].spend == last.spend
        assert result.snapshot[0].at == last.at

    def test_a_slice_without_a_closing_row_stays_in_the_snapshot_with_the_instant_of_its_last_row(self) -> None:
        last = EventMother.advancing_again(minutes_later=7)
        reader = ScriptedEventReader(EventBatch(events=(EventMother.advancing(), last), cursor=EventCursor(offset=10)))

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert [event.at for event in result.snapshot] == [EventMother.advancing().at + timedelta(minutes=7)]

    def test_two_slices_have_one_entry_each(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(EventMother.advancing(), EventMother.advancing_in_another_slice()),
                cursor=EventCursor(offset=10),
            )
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert [event.slice_id for event in result.snapshot] == ["slice-05", "slice-06"]

    def test_the_same_slice_id_in_two_repos_is_two_entries(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(EventMother.advancing(), EventMother.advancing_in_another_repo()),
                cursor=EventCursor(offset=10),
            )
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert len(result.snapshot) == 2


class TestWhatCountsAsAChange:
    def test_three_consecutive_rows_of_a_slice_with_the_same_step_and_closure_make_exactly_one_change(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(
                    EventMother.advancing(),
                    EventMother.advancing_again(minutes_later=1),
                    EventMother.advancing_again(minutes_later=2),
                ),
                cursor=EventCursor(offset=10),
            )
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert len(result.changes) == 1

    def test_a_row_whose_step_and_closure_differ_from_the_previous_row_of_its_slice_is_a_change(self) -> None:
        waiting = EventMother.waiting_on_a_machine()
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(), waiting), cursor=EventCursor(offset=10))
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert result.changes == (EventMother.advancing(), waiting)

    def test_a_round_without_changes_on_the_same_step_and_closure_is_a_change_so_it_reaches_the_screen(self) -> None:
        empty_round = EventMother.round_without_changes()
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing(), empty_round), cursor=EventCursor(offset=10))
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert result.changes == (EventMother.advancing(), empty_round)

    def test_a_closing_row_that_goes_from_blocked_to_merged_on_the_same_step_is_a_change_and_the_snapshot_ends_merged(
        self,
    ) -> None:
        blocked = EventMother.blocked_by_the_judge()
        merged = EventMother.closed()
        reader = ScriptedEventReader(EventBatch(events=(merged,), cursor=EventCursor(offset=20)))

        result = FollowEvents(reader=reader).execute(
            FollowEventsParams(cursor=EventCursor(offset=10), snapshot=(blocked,))
        )

        assert result.changes == (merged,)
        assert [event.closure for event in result.snapshot] == [Closure.merged()]

    def test_interleaved_slices_are_compared_each_against_its_own_previous_row(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(
                events=(
                    EventMother.advancing(),
                    EventMother.advancing_in_another_slice(),
                    EventMother.advancing_again(minutes_later=1),
                ),
                cursor=EventCursor(offset=10),
            )
        )

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert len(result.changes) == 2

    def test_a_first_row_equal_to_the_one_the_previous_snapshot_holds_is_not_a_change(self) -> None:
        reader = ScriptedEventReader(
            EventBatch(events=(EventMother.advancing_again(minutes_later=3),), cursor=EventCursor(offset=20))
        )

        result = FollowEvents(reader=reader).execute(
            FollowEventsParams(cursor=EventCursor(offset=10), snapshot=(EventMother.advancing(),))
        )

        assert result.changes == ()
        assert result.snapshot == (EventMother.advancing_again(minutes_later=3),)


class TestWhatTheQueryDoesNotDecide:
    def test_a_slice_never_closed_is_not_judged_dead_it_simply_keeps_its_last_row(self) -> None:
        reader = ScriptedEventReader(EventBatch(events=(EventMother.advancing(),), cursor=EventCursor(offset=10)))

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert result.snapshot == (EventMother.advancing(),)


class TestWhereReadingResumes:
    def test_the_reader_is_asked_from_the_cursor_it_was_given(self) -> None:
        reader = ScriptedEventReader(EventBatch(events=(), cursor=EventCursor(offset=10)))

        FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor(offset=10)))

        assert reader.cursors == [EventCursor(offset=10)]

    def test_the_cursor_the_reader_returns_is_the_one_the_result_hands_back(self) -> None:
        reader = ScriptedEventReader(EventBatch(events=(), cursor=EventCursor(offset=99)))

        result = FollowEvents(reader=reader).execute(FollowEventsParams(cursor=EventCursor.start()))

        assert result.cursor == EventCursor(offset=99)


class TestFilteringByRepo:
    @pytest.fixture
    def reader(self) -> ScriptedEventReader:
        return ScriptedEventReader(
            EventBatch(
                events=(EventMother.advancing(), EventMother.advancing_in_another_repo()),
                cursor=EventCursor(offset=10),
            )
        )

    def test_only_the_events_of_that_repo_reach_the_snapshot_and_the_changes(self, reader: ScriptedEventReader) -> None:
        result = FollowEvents(reader=reader).execute(
            FollowEventsParams(cursor=EventCursor.start(), repo=EventMother.ANOTHER_REPO)
        )

        assert result.snapshot == (EventMother.advancing_in_another_repo(),)
        assert result.changes == (EventMother.advancing_in_another_repo(),)

    def test_filtering_does_not_stop_the_cursor_from_moving_past_the_rows_of_other_repos(
        self, reader: ScriptedEventReader
    ) -> None:
        result = FollowEvents(reader=reader).execute(
            FollowEventsParams(cursor=EventCursor.start(), repo=EventMother.ANOTHER_REPO)
        )

        assert result.cursor == EventCursor(offset=10)
