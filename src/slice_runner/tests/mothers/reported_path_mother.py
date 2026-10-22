from __future__ import annotations

from slice_runner.domain.path_kind import PathKind
from slice_runner.domain.reported_path import ReportedPath


class ReportedPathMother:
    @staticmethod
    def production_file() -> ReportedPath:
        return ReportedPath(path="src/slice_runner/domain/staged_hygiene.py", kind=PathKind.PRODUCTION)

    @staticmethod
    def test_file() -> ReportedPath:
        return ReportedPath(path="src/slice_runner/tests/application/actions/test_stage_slice.py", kind=PathKind.TEST)

    @staticmethod
    def plan() -> ReportedPath:
        return ReportedPath(path="docs/superpowers/plans/2026-08-04-entrega-de-la-slice.md", kind=PathKind.PRODUCTION)

    @staticmethod
    def production_file_with_a_dot_segment() -> ReportedPath:
        return ReportedPath(path="./src/slice_runner/domain/staged_hygiene.py", kind=PathKind.PRODUCTION)
