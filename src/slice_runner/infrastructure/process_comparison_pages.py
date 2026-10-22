from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.comparison_pages import ComparisonPages
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.infrastructure.comparison_page import ComparisonPage

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures
    from slice_runner.infrastructure.process import Process


class ProcessComparisonPages(ComparisonPages):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def write(
        self, *, worktree: str, designs: tuple[Design, ...], captures: DesignCaptures | MissingDesignCaptures
    ) -> None:
        page = ComparisonPage.of(designs=designs, captures=captures, contents=self._contents_of(captures))
        self._run(["mkdir", "-p", DesignCapturesDirectory.of(worktree)], stdin="")
        self._run(["tee", DesignCapturesDirectory.comparison_of(worktree)], stdin=page)

    def _contents_of(self, captures: DesignCaptures | MissingDesignCaptures) -> dict[str, str]:
        if not isinstance(captures, DesignCaptures):
            return {}

        return {
            capture.path: self._run(["cat", capture.path], stdin="")
            for capture in captures.captures
            if capture.path.endswith(ComparisonPage.HTML_CAPTURE_SUFFIX)
        }

    def _run(self, argv: list[str], *, stdin: str) -> str:
        output = self._process.run(argv, stdin=stdin)
        if output.code != 0:
            raise OSError(f"the comparison page could not be mounted: {output.reason(tool=argv[0])}")

        return output.stdout
