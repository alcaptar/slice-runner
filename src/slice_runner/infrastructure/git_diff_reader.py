from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError
from slice_runner.domain.slice_diff import SliceDiff
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitDiffReader(DiffReader):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def read(self, *, worktree: str, base: str) -> SliceDiff:
        files = self._staged_names(worktree=worktree, base=base)
        if not files:
            raise EmptyIndexError(f"nothing staged against {base}: nothing to verify (forgotten git add?)")

        return SliceDiff(
            text=self._diffed(worktree=worktree, base=base, extra=[]),
            files=files,
            stats=self._stats(worktree=worktree, base=base),
        )

    def dirty(self, *, worktree: str) -> tuple[str, ...]:
        argv = ["git", "-C", worktree, "status", "--porcelain", "--untracked-files=all"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return tuple(line[3:] for line in output.stdout.splitlines() if line.strip() and line[1] != " ")

    def _staged_names(self, *, worktree: str, base: str) -> tuple[str, ...]:
        listing = self._diffed(worktree=worktree, base=base, extra=["--name-only"])

        return tuple(line for line in listing.splitlines() if line.strip())

    def _stats(self, *, worktree: str, base: str) -> DiffStats:
        listing = self._diffed(worktree=worktree, base=base, extra=["--numstat"])
        rows = tuple(line.split("\t") for line in listing.splitlines() if line.strip())

        return DiffStats(
            files_changed=len(rows),
            lines_added=sum(self._lines(added) for added, _, _ in rows),
            lines_deleted=sum(self._lines(deleted) for _, deleted, _ in rows),
        )

    @staticmethod
    def _lines(count: str) -> int:
        return 0 if count == "-" else int(count)

    def _diffed(self, *, worktree: str, base: str, extra: list[str]) -> str:
        argv = ["git", "-C", worktree, "diff", "--cached", *extra, "--merge-base", base]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableRepoOrBaseError(
                f"could not diff {worktree!r} against {base!r}: {output.reason(tool=argv[0])}"
            )

        return output.stdout
