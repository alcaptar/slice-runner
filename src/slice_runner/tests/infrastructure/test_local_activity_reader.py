from __future__ import annotations

from slice_runner.domain.event_cursor import EventCursor
from slice_runner.infrastructure.local_activity_log import LocalActivityLog
from slice_runner.infrastructure.local_activity_reader import LocalActivityReader
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.activity_mother import ActivityMother

_COORDINATES = ActivityMother.of_the_implementer_editing().coordinates


class TestReadingTheActivityOfASlice(WithTheDurableStoresOutOfTheRealHome):
    def _log(self) -> LocalActivityLog:
        return LocalActivityLog(clock=self.frozen_at(ActivityMother.AT))

    def test_a_slice_that_never_had_activity_reads_as_nothing_at_the_cursor_it_was_asked_from(self) -> None:
        batch = LocalActivityReader().read_since(_COORDINATES, EventCursor(offset=7))

        assert (batch.activities, batch.cursor) == ((), EventCursor(offset=7))

    def test_the_first_read_brings_every_line_and_the_next_only_those_written_after(self) -> None:
        log = self._log()
        log.record(ActivityMother.of_the_implementer_editing())
        reader = LocalActivityReader()
        first = reader.read_since(_COORDINATES, EventCursor.start())

        log.record(ActivityMother.of_the_implementer_editing())
        second = reader.read_since(_COORDINATES, first.cursor)

        assert len(first.activities) == 1
        assert second.activities == (ActivityMother.observed(ActivityMother.of_the_implementer_editing()),)

    def test_a_file_emptied_and_refilled_with_less_than_the_cursor_is_read_again_from_the_start(self) -> None:
        log = self._log()
        log.record(ActivityMother.of_the_implementer_editing())
        log.record(ActivityMother.of_the_implementer_editing())
        reader = LocalActivityReader()
        first = reader.read_since(_COORDINATES, EventCursor.start())

        log.restart(_COORDINATES)
        log.record(ActivityMother.of_the_judge_reading())
        second = reader.read_since(_COORDINATES, first.cursor)

        assert [seen.activity.tool for seen in second.activities] == ["Read"]

    def test_the_activity_of_another_slice_is_not_read(self) -> None:
        self._log().record(ActivityMother.of_another_slice())

        batch = LocalActivityReader().read_since(_COORDINATES, EventCursor.start())

        assert batch.activities == ()
