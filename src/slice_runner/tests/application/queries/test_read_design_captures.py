from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.read_design_captures import ReadDesignCaptures, ReadDesignCapturesParams
from slice_runner.domain.design_capture_store import DesignCaptureStore
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.design_mother import DesignMother

_WORKTREE = "/repos/project"


class TestReadDesignCaptures:
    @pytest.fixture
    def store(self) -> Mock:
        store: Mock = create_autospec(DesignCaptureStore, spec_set=True, instance=True)
        store.read.return_value = DesignCapturesMother.of_the_board_and_the_detail()
        return store

    @pytest.fixture
    def query(self, store: Mock) -> ReadDesignCaptures:
        return ReadDesignCaptures(captures=store)

    def test_a_slice_with_designs_gets_what_the_store_reads_of_its_worktree(
        self, query: ReadDesignCaptures, store: Mock
    ) -> None:
        designs = (DesignMother.board(), DesignMother.detail())

        read = query.execute(ReadDesignCapturesParams(worktree=_WORKTREE, designs=designs))

        assert read == DesignCapturesMother.of_the_board_and_the_detail()
        store.read.assert_called_once_with(worktree=_WORKTREE, designs=designs)

    def test_captures_declared_missing_come_back_with_their_reason(
        self, query: ReadDesignCaptures, store: Mock
    ) -> None:
        store.read.return_value = DesignCapturesMother.missing()

        read = query.execute(ReadDesignCapturesParams(worktree=_WORKTREE, designs=(DesignMother.board(),)))

        assert read == DesignCapturesMother.missing()

    def test_a_slice_that_cites_no_design_reads_nothing_and_gets_no_captures(
        self, query: ReadDesignCaptures, store: Mock
    ) -> None:
        read = query.execute(ReadDesignCapturesParams(worktree=_WORKTREE, designs=()))

        assert read == DesignCapturesMother.none()
        store.read.assert_not_called()
