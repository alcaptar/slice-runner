from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.debt_ledger import DebtDeclaration
from slice_runner.domain.exceptions import UnreadableDebtLedgerError
from slice_runner.infrastructure.local_debt_ledger import LocalDebtLedger
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.mothers.debt_entry_mother import DebtEntryMother

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.slice_coordinates import SliceCoordinates

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class WrittenDebtLedger:
    @staticmethod
    def rows_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "debt.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestARecordedDeclarationIsWrittenImmediately(WithTheDurableStoresOutOfTheRealHome):
    def test_recording_a_declaration_appends_a_row_with_the_slices_coordinates_and_what_was_left_out(
        self, tmp_path: Path
    ) -> None:
        LocalDebtLedger(clock=self.frozen_at()).record(
            DebtEntryMother.of_the_slice(left_out=("no cubri el caso de un binario",))
        )

        assert WrittenDebtLedger.rows_under(tmp_path) == [
            {
                "repo": DebtEntryMother.REPO,
                "issue": DebtEntryMother.ISSUE,
                "slice_id": DebtEntryMother.SLICE_ID,
                "left_out": ["no cubri el caso de un binario"],
                "ts": _STAMP.isoformat(),
            }
        ]

    def test_an_empty_left_out_list_is_still_written_instead_of_staying_silent(self, tmp_path: Path) -> None:
        LocalDebtLedger(clock=self.frozen_at()).record(DebtEntryMother.of_the_slice(left_out=()))

        assert WrittenDebtLedger.rows_under(tmp_path)[0]["left_out"] == []


class AskingTheLedgerAboutOneSlice(WithTheDurableStoresOutOfTheRealHome):
    @staticmethod
    def _coordinates() -> SliceCoordinates:
        return DebtEntryMother.coordinates()


class TestTheDeclarationsOfTheSlice(AskingTheLedgerAboutOneSlice):
    def test_a_slice_with_no_declaration_recorded_answers_with_nothing(self) -> None:
        ledger = LocalDebtLedger(clock=self.frozen_at())

        assert ledger.declarations_of_the_slice(self._coordinates()) == ()

    def test_two_rounds_that_declared_different_gaps_are_both_read_back(self) -> None:
        ledger = LocalDebtLedger(clock=self.frozen_at())

        ledger.record(DebtEntryMother.of_the_slice(left_out=("no cubri el caso de un binario",)))
        ledger.record(DebtEntryMother.of_the_slice(left_out=("falta el caso de rename",)))

        assert ledger.declarations_of_the_slice(self._coordinates()) == (
            DebtDeclaration(left_out=("no cubri el caso de un binario",)),
            DebtDeclaration(left_out=("falta el caso de rename",)),
        )

    def test_a_declaration_of_a_different_slice_is_left_out(self) -> None:
        ledger = LocalDebtLedger(clock=self.frozen_at())

        ledger.record(DebtEntryMother.of_the_slice(slice_id="slice-99", left_out=("otra slice",)))

        assert ledger.declarations_of_the_slice(self._coordinates()) == ()


class TestARowFromAnotherGenerationIsRejected(WithTheDurableStoresOutOfTheRealHome):
    def test_a_row_missing_left_out_is_rejected_naming_the_generation(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "slice-runner" / "runs" / "debt.jsonl"
        ledger_path.parent.mkdir(parents=True)
        without_left_out = {
            "ts": _STAMP.isoformat(),
            "repo": DebtEntryMother.REPO,
            "issue": DebtEntryMother.ISSUE,
            "slice_id": DebtEntryMother.SLICE_ID,
        }
        ledger_path.write_text(json.dumps(without_left_out) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableDebtLedgerError, match="generation"):
            LocalDebtLedger(clock=self.frozen_at()).declarations_of_the_slice(DebtEntryMother.coordinates())
