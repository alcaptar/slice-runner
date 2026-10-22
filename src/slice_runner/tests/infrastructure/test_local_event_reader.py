from __future__ import annotations

import json

import pytest

from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.exceptions import UnreadableEventLogError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.local_event_log import LocalEventLog
from slice_runner.infrastructure.local_event_reader import LocalEventReader
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.event_mother import EventMother


class TestReadingFromWhereTheLastReadStopped(WithTheDurableStoresOutOfTheRealHome):
    def test_a_ledger_that_does_not_exist_yet_reads_as_no_events_at_the_start(self) -> None:
        batch = LocalEventReader().read_since(EventCursor.start())

        assert (batch.events, batch.cursor) == ((), EventCursor.start())

    def test_the_first_read_brings_every_event_written_so_far_as_domain_events(self) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        log.emit(EventMother.closed())

        batch = LocalEventReader().read_since(EventCursor.start())

        assert batch.events == (EventMother.advancing(), EventMother.closed())

    def test_a_second_read_with_the_returned_cursor_brings_only_the_rows_appended_after_the_first(self) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        reader = LocalEventReader()
        first = reader.read_since(EventCursor.start())

        log.emit(EventMother.closed())
        second = reader.read_since(first.cursor)

        assert second.events == (EventMother.closed(),)

    def test_a_read_with_nothing_new_brings_no_events_and_the_same_cursor(self) -> None:
        LocalEventLog().emit(EventMother.advancing())
        reader = LocalEventReader()
        first = reader.read_since(EventCursor.start())

        second = reader.read_since(first.cursor)

        assert (second.events, second.cursor) == ((), first.cursor)

    def test_the_cursor_moves_past_the_bytes_read_and_not_past_a_row_still_being_written(self) -> None:
        LocalEventLog().emit(EventMother.advancing())
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        complete = ledger.stat().st_size
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write('{"slice_id": "slice-05"')

        batch = LocalEventReader().read_since(EventCursor.start())

        assert batch.cursor == EventCursor(offset=complete)
        assert batch.events == (EventMother.advancing(),)

    def test_a_row_finished_after_being_half_written_is_read_whole_by_the_next_read(self) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        reader = LocalEventReader()
        first = reader.read_since(EventCursor.start())
        whole = EventPayload.from_domain(EventMother.closed()).model_dump_json(by_alias=True)
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(whole[:20])
        assert reader.read_since(first.cursor).events == ()
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(f"{whole[20:]}\n")

        second = reader.read_since(first.cursor)

        assert second.events == (EventMother.closed(),)


class TestARowThisGenerationDidNotWrite(WithTheDurableStoresOutOfTheRealHome):
    def test_a_line_that_is_not_json_is_refused_naming_where_it_starts(self) -> None:
        LocalEventLog().emit(EventMother.advancing())
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        start = ledger.stat().st_size
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write("not json\n")

        with pytest.raises(UnreadableEventLogError, match=f"offset {start}"):
            LocalEventReader().read_since(EventCursor.start())

    def test_a_row_with_a_key_nobody_declared_is_refused(self) -> None:
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text('{"ts": "2024-01-01T00:00:00+00:00", "surprise": 1}\n', encoding="utf-8")

        with pytest.raises(UnreadableEventLogError, match="not one this program wrote in this generation"):
            LocalEventReader().read_since(EventCursor.start())


class TestARowOfTheRetiredUnderstandStep(WithTheDurableStoresOutOfTheRealHome):
    def test_a_row_written_when_the_run_still_understood_is_read_back_as_the_understand_step(self) -> None:
        row = {**EventPayload.from_domain(EventMother.advancing()).to_contract(), "step": "understand"}
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")

        batch = LocalEventReader().read_since(EventCursor.start())

        assert [event.step for event in batch.events] == [Step.UNDERSTAND]


class TestARowOfTheRetiredStatusGeneration(WithTheDurableStoresOutOfTheRealHome):
    def test_a_line_with_a_status_field_is_an_error_that_names_the_line(self) -> None:
        log = LocalEventLog()
        log.emit(EventMother.advancing())
        ledger = DurableLedger(name=LocalEventLog.LEDGER, row=EventPayload).path()
        first_line = ledger.read_text(encoding="utf-8")
        row = {**EventPayload.from_domain(EventMother.advancing()).to_contract(), "status": "advancing"}
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")

        with pytest.raises(UnreadableEventLogError, match=rf"offset {len(first_line.encode('utf-8'))}.*`status`"):
            LocalEventReader().read_since(EventCursor.start())
