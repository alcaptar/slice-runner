from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.exceptions import PermissionDeniedError
from slice_runner.domain.implementation import Implementation
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.harness_invocation_runner import HarnessCallSubject
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.report_payload import ImplementationReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocationRunner
    from slice_runner.infrastructure.harness_output import HarnessOutput


class ClaudeImplementer(Implementer):
    def __init__(self, *, calls: HarnessInvocationRunner, reader: SourceReader) -> None:
        self._calls = calls
        self._reader = reader

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment, reader=self._reader)
        envelope = self._calls.call(
            invocation,
            step=Step.IMPLEMENT,
            subject=HarnessCallSubject(
                coordinates=SliceCoordinates(
                    repo=assignment.repo, issue=assignment.issue, slice_id=CanonicalSliceId.of_text(assignment.slice_id)
                ),
                worktree=assignment.worktree,
            ),
        )
        with envelope.measuring():
            self._reject_denials(envelope)
            report = ImplementationReportPayload.from_dict(envelope.structured())

        return Implementation(
            paths=report.to_domain(),
            left_out=tuple(report.left_out),
            deviations=tuple(report.deviations),
            spend=envelope.to_domain(),
        )

    @staticmethod
    def _reject_denials(envelope: HarnessOutput) -> None:
        denials = tuple(denial.denied_action for denial in envelope.permission_denials)
        if denials:
            raise PermissionDeniedError(
                f"the harness denied {len(denials)} permission(s), so there is no report to trust: {', '.join(denials)}"
            )
