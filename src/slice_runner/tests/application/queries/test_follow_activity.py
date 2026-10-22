from __future__ import annotations

from slice_runner.application.queries.follow_activity import FollowActivity, FollowActivityParams
from slice_runner.domain.activity_cursors import ActivityCursors
from slice_runner.domain.activity_reader import ActivityBatch
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.tests.doubles import RecordedActivityReader
from slice_runner.tests.mothers.activity_mother import ActivityMother
from slice_runner.tests.mothers.event_mother import EventMother


class TestFollowingTheActivityOfTheSlicesInTheSnapshot:
    _FOLLOWED = ActivityMother.coordinates_of_the_followed_slice()

    def _batch(self, *, offset: int) -> ActivityBatch:
        activity = ActivityMother.in_the_followed_slice(tool="Edit", target="a.py")

        return ActivityBatch(activities=(ActivityMother.observed(activity),), cursor=EventCursor(offset=offset))

    def test_the_activities_of_every_slice_in_the_snapshot_come_back_and_the_cursor_moves_past_them(self) -> None:
        reader = RecordedActivityReader({self._FOLLOWED: self._batch(offset=40)})

        result = FollowActivity(reader=reader).execute(
            FollowActivityParams(snapshot=(EventMother.advancing(),), cursors=ActivityCursors())
        )

        assert [seen.activity.tool for seen in result.activities] == ["Edit"]
        assert result.cursors.of(self._FOLLOWED) == EventCursor(offset=40)

    def test_each_slice_is_read_from_the_cursor_it_left_off_at_and_no_other(self) -> None:
        reader = RecordedActivityReader({})
        cursors = ActivityCursors().moved(self._FOLLOWED, EventCursor(offset=40))

        FollowActivity(reader=reader).execute(
            FollowActivityParams(
                snapshot=(EventMother.advancing(), EventMother.advancing_in_another_slice()), cursors=cursors
            )
        )

        assert [(read[0].slice_id.text, read[1]) for read in reader.reads] == [
            ("slice-05", EventCursor(offset=40)),
            ("slice-06", EventCursor.start()),
        ]
