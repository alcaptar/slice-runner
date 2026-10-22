from __future__ import annotations

from slice_runner.domain.implementation import Implementation
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.reported_path_mother import ReportedPathMother


class ImplementationMother:
    @staticmethod
    def of_two_paths() -> Implementation:
        return Implementation(
            paths=(ReportedPathMother.production_file(), ReportedPathMother.test_file()),
            left_out=(),
            deviations=(),
            spend=HarnessSpendMother.of_the_implementer_call(),
        )

    @staticmethod
    def with_debt() -> Implementation:
        return Implementation(
            paths=(ReportedPathMother.production_file(), ReportedPathMother.test_file()),
            left_out=("el cableado del subcomando queda para otra slice",),
            deviations=(),
            spend=HarnessSpendMother.of_the_implementer_call(),
        )

    @staticmethod
    def with_two_deviations() -> Implementation:
        return Implementation(
            paths=(ReportedPathMother.production_file(), ReportedPathMother.test_file()),
            left_out=(),
            deviations=(
                "el puerto no admite la firma decidida porque ya la consume otro adaptador",
                "la excepcion hereda de OSError y no de ValueError porque el subproceso la lanza",
            ),
            spend=HarnessSpendMother.of_the_implementer_call(),
        )
