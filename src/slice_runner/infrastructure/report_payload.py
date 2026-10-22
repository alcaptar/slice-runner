from __future__ import annotations

from typing import Self

from slice_runner.domain.exceptions import InvalidImplementationReportError
from slice_runner.domain.path_kind import PathKind
from slice_runner.domain.reported_path import ReportedPath
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema


class ReportedPathPayload(ContractModel):
    path: str
    kind: PathKind

    def to_domain(self) -> ReportedPath:
        return ReportedPath(path=self.path, kind=self.kind)


class ImplementationReportPayload(ContractModel):
    paths: list[ReportedPathPayload]
    left_out: list[str]
    deviations: list[str]

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the implementer did not emit the report the brief asked for", InvalidImplementationReportError
        )

    def to_domain(self) -> tuple[ReportedPath, ...]:
        return tuple(path.to_domain() for path in self.paths)
