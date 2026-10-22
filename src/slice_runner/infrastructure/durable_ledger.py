from __future__ import annotations

import json
from abc import abstractmethod
from typing import TYPE_CHECKING, ClassVar, Generic, Self, TypeVar

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


class LedgerRow(ContractModel):
    pass


class ReadableLedgerRow(LedgerRow):
    UNREADABLE: ClassVar[type[ValueError]]

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, object]) -> Self: ...


_Row = TypeVar("_Row", bound=LedgerRow)
_Read = TypeVar("_Read", bound=ReadableLedgerRow)


class DurableLedger(Generic[_Row]):
    ROOT: ClassVar[tuple[str, ...]] = ("slice-runner", "runs")

    def __init__(self, *, name: str, row: type[_Row]) -> None:
        self._name = name
        self._row = row

    @classmethod
    def root(cls) -> Path:
        return ClaudeConfig.root().joinpath(*cls.ROOT)

    def path(self) -> Path:
        return self.root() / f"{self._name}.jsonl"

    def append(self, row: _Row) -> None:
        ledger = self.path()
        ledger.parent.mkdir(parents=True, exist_ok=True)

        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(f"{json.dumps(row.to_contract(), ensure_ascii=False)}\n")


class ReadableDurableLedger(DurableLedger[_Read]):
    def rows(self) -> Iterator[_Read]:
        yield from self.rows_where(self._anything)

    def rows_where(self, keep: Callable[[dict[str, object]], bool]) -> Iterator[_Read]:
        for number, line in self._numbered_lines():
            data = self._decoded(line, number)
            if not keep(data):
                continue

            yield self._row.from_dict(data)

    def last_row_where(self, keep: Callable[[dict[str, object]], bool]) -> _Read | None:
        latest: dict[str, object] | None = None
        for number, line in self._numbered_lines():
            data = self._decoded(line, number)
            if keep(data):
                latest = data

        return self._row.from_dict(latest) if latest is not None else None

    def rows_from(self, offset: int) -> tuple[tuple[_Read, ...], int]:
        ledger = self.path()
        if not ledger.exists():
            return (), offset

        with ledger.open("rb") as stream:
            stream.seek(offset)
            pending = stream.read()

        rows: list[_Read] = []
        position = offset
        for raw in pending.splitlines(keepends=True):
            if not raw.endswith(b"\n"):
                break
            if raw.strip():
                rows.append(self._row_at(raw, position))
            position += len(raw)

        return tuple(rows), position

    def _row_at(self, raw: bytes, position: int) -> _Read:
        where = f"offset {position}"
        data = self._decoded(raw.decode("utf-8"), where)
        try:
            return self._row.from_dict(data)
        except self._row.UNREADABLE as error:
            raise self._row.UNREADABLE(f"the {self._name} ledger line at {where}: {error}") from error

    @staticmethod
    def _anything(data: dict[str, object]) -> bool:
        return True

    def _numbered_lines(self) -> Iterator[tuple[int, str]]:
        ledger = self.path()
        if not ledger.exists():
            return

        for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                yield number, line

    def _decoded(self, line: str, number: int | str) -> dict[str, object]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise self._row.UNREADABLE(
                f"the {self._name} ledger has a line at {number} that is not JSON: {error}"
            ) from error
        if not isinstance(data, dict):
            raise self._row.UNREADABLE(
                f"the {self._name} ledger has a line at {number} that has to be an object, not {type(data).__name__}"
            )

        return {str(key): value for key, value in data.items()}
