from __future__ import annotations

from typing import Self

from slice_runner.domain.round_budget import RoundBudget
from slice_runner.domain.rounds import Rounds
from slice_runner.infrastructure.contract_model import ContractModel


class FollowRoundPayload(ContractModel):
    used: int
    limit: int

    @classmethod
    def from_domain(cls, round_budget: RoundBudget) -> Self:
        return cls(used=round_budget.used, limit=round_budget.limit)

    def to_domain(self) -> RoundBudget:
        return RoundBudget(used=self.used, limit=self.limit)


class FollowRoundsPayload(ContractModel):
    controls: FollowRoundPayload
    hygiene: FollowRoundPayload
    judge: FollowRoundPayload
    ci: FollowRoundPayload
    ci_indeterminate: FollowRoundPayload
    catch_up: FollowRoundPayload

    @classmethod
    def from_domain(cls, rounds: Rounds) -> Self:
        return cls(
            controls=FollowRoundPayload.from_domain(rounds.controls),
            hygiene=FollowRoundPayload.from_domain(rounds.hygiene),
            judge=FollowRoundPayload.from_domain(rounds.judge),
            ci=FollowRoundPayload.from_domain(rounds.ci),
            ci_indeterminate=FollowRoundPayload.from_domain(rounds.ci_indeterminate),
            catch_up=FollowRoundPayload.from_domain(rounds.catch_up),
        )

    def to_domain(self) -> Rounds:
        return Rounds(
            controls=self.controls.to_domain(),
            hygiene=self.hygiene.to_domain(),
            judge=self.judge.to_domain(),
            ci=self.ci.to_domain(),
            ci_indeterminate=self.ci_indeterminate.to_domain(),
            catch_up=self.catch_up.to_domain(),
        )
