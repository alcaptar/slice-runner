from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from slice_runner.domain.debt_ledger import DebtDeclaration


@dataclass(frozen=True, kw_only=True, slots=True)
class DeclaredDebt:
    declared: bool = False
    left_out: tuple[str, ...] = field(default=())

    @classmethod
    def nothing(cls) -> Self:
        return cls()

    @classmethod
    def of_declarations(cls, declarations: tuple[DebtDeclaration, ...]) -> Self:
        if not declarations:
            return cls.nothing()

        seen: dict[str, None] = {}
        for declaration in declarations:
            for item in declaration.left_out:
                seen.setdefault(item)

        return cls(declared=True, left_out=tuple(seen))
