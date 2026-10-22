from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadableRunError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.run import Run
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.discarded_call_payload import DiscardedCallPayload
from slice_runner.infrastructure.requested_change_payload import RequestedChangePayload
from slice_runner.infrastructure.spend_payload import SpendPayload

Spent = Annotated[int, Field(strict=True, ge=0)]


class RunPayload(ContractModel):
    step: Step
    corrected: str | None = None
    alignment: str | None = None
    understanding_pending: Annotated[bool, Field(strict=True)] | None = None
    retry_instruction: str = ""
    tree_unexpected: bool = False
    previous_call_died: bool = False
    catching_up_the_branch: bool = False
    control_retries: Spent = 0
    hygiene_retries: Spent = 0
    verify_retries: Spent = 0
    ci_retries: Spent = 0
    catch_up_retries: Spent = 0
    indeterminate_ticks: Spent = 0
    verify_discards: Spent = 0
    understand_discards: Spent | None = None
    implement_discards: Spent = 0
    control_rounds_logged: Spent = 0
    verify_rounds_logged: Spent = 0
    last_reviewed_id: Spent = 0
    requested_changes: list[RequestedChangePayload] = Field(default_factory=list)
    discarded_call: DiscardedCallPayload | None = None
    spend: SpendPayload | None = None
    spend_before_reopening: SpendPayload | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the execution state block is not one this program can read", UnreadableRunError)

    @classmethod
    def from_domain(cls, run: Run) -> Self:
        return cls(
            step=run.step,
            retry_instruction=run.retry_instruction,
            tree_unexpected=run.tree_unexpected,
            previous_call_died=run.previous_call_died,
            catching_up_the_branch=run.catching_up_the_branch,
            control_retries=run.control_retries,
            hygiene_retries=run.hygiene_retries,
            verify_retries=run.verify_retries,
            ci_retries=run.ci_retries,
            catch_up_retries=run.catch_up_retries,
            indeterminate_ticks=run.indeterminate_ticks,
            verify_discards=run.verify_discards,
            implement_discards=run.implement_discards,
            control_rounds_logged=run.control_rounds_logged,
            verify_rounds_logged=run.verify_rounds_logged,
            last_reviewed_id=run.last_reviewed_id,
            requested_changes=[RequestedChangePayload.from_domain(change) for change in run.requested_changes],
            discarded_call=DiscardedCallPayload.from_domain(run.discarded_call)
            if run.discarded_call is not None
            else None,
            spend=SpendPayload.from_domain(run.spend) if run.spend.measured else None,
        )

    def to_domain(self) -> Run:
        return Run(
            step=self.step,
            retry_instruction=self.retry_instruction,
            tree_unexpected=self.tree_unexpected,
            previous_call_died=self.previous_call_died,
            catching_up_the_branch=self.catching_up_the_branch,
            control_retries=self.control_retries,
            hygiene_retries=self.hygiene_retries,
            verify_retries=self.verify_retries,
            ci_retries=self.ci_retries,
            catch_up_retries=self.catch_up_retries,
            indeterminate_ticks=self.indeterminate_ticks,
            verify_discards=self.verify_discards,
            implement_discards=self.implement_discards,
            control_rounds_logged=self.control_rounds_logged,
            verify_rounds_logged=self.verify_rounds_logged,
            last_reviewed_id=self.last_reviewed_id,
            requested_changes=tuple(payload.to_domain() for payload in self.requested_changes),
            discarded_call=self.discarded_call.to_domain() if self.discarded_call is not None else None,
            spend=self.spend.to_domain() if self.spend is not None else HarnessSpend.nothing(),
        )
