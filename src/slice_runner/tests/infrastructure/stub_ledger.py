from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from slice_runner.infrastructure.durable_ledger import LedgerRow

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import ModuleType

    import pytest

_Row = TypeVar("_Row", bound=LedgerRow)


class StubLedger(Generic[_Row]):
    def __init__(self, *, name: str, row: type[_Row]) -> None:
        self.name = name
        self.row = row
        self.appended: list[_Row] = []

    def append(self, row: _Row) -> None:
        self.appended.append(row)

    def rows(self) -> Iterator[_Row]:
        yield from self.appended

    def rows_where(self, keep: Callable[[dict[str, object]], bool]) -> Iterator[_Row]:
        for row in self.appended:
            if keep(row.to_contract()):
                yield row


class WiredStubLedgers:
    _PATCHED_NAMES = ("DurableLedger", "ReadableDurableLedger")

    @staticmethod
    def on(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[StubLedger[Any]]:
        created: list[StubLedger[Any]] = []

        def factory(*, name: str, row: type[Any]) -> StubLedger[Any]:
            stub = StubLedger(name=name, row=row)
            created.append(stub)
            return stub

        for attribute in WiredStubLedgers._PATCHED_NAMES:
            if hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, factory)

        return created
