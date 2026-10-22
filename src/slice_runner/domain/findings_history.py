from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from slice_runner.domain.corpus import JudgedRound
    from slice_runner.domain.finding import Finding


@dataclass(frozen=True, kw_only=True, slots=True)
class FindingAppearance:
    round: int
    finding: Finding


@dataclass(frozen=True, kw_only=True, slots=True)
class GroupedFinding:
    rule: str
    path: str
    appearances: tuple[FindingAppearance, ...]

    @property
    def last_appearance(self) -> FindingAppearance:
        return max(self.appearances, key=lambda appearance: appearance.round)

    def seen_in_the_last_round(self, last_round: int) -> bool:
        return self.last_appearance.round == last_round


@dataclass(frozen=True, kw_only=True, slots=True)
class FindingsHistory:
    last_round: int = 0
    composed_rounds: int = 0
    entries: tuple[GroupedFinding, ...] = field(default=())

    @classmethod
    def of_rounds(cls, rounds: tuple[JudgedRound, ...]) -> Self:
        appearances_of: dict[tuple[str, str], list[FindingAppearance]] = {}
        order: list[tuple[str, str]] = []
        for judged in rounds:
            for finding in judged.findings:
                key = (finding.rule, finding.path)
                if key not in appearances_of:
                    appearances_of[key] = []
                    order.append(key)
                appearances_of[key].append(FindingAppearance(round=judged.round, finding=finding))

        entries = tuple(
            GroupedFinding(rule=rule, path=path, appearances=tuple(appearances_of[(rule, path)]))
            for rule, path in order
        )
        last_round = max((judged.round for judged in rounds), default=0)

        return cls(last_round=last_round, composed_rounds=len(rounds), entries=entries)

    @property
    def every_appearance(self) -> tuple[FindingAppearance, ...]:
        return tuple(
            sorted(
                (appearance for entry in self.entries for appearance in entry.appearances),
                key=lambda appearance: appearance.round,
            )
        )

    @property
    def appearances_of_the_last_round(self) -> tuple[FindingAppearance, ...]:
        return tuple(appearance for appearance in self.every_appearance if appearance.round == self.last_round)

    @property
    def is_empty(self) -> bool:
        return not self.entries
