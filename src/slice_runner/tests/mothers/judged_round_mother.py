from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.corpus import JudgedRound

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class JudgedRoundMother:
    @staticmethod
    def of_the_round(round: int, *findings: Finding) -> JudgedRound:
        return JudgedRound(round=round, findings=findings)
