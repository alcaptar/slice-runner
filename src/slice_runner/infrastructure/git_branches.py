from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.branches import Branches
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitBranches(Branches):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def commits_behind_remote(self, *, worktree: str, base: str) -> int:
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "rev-list", "--count", f"{base}..origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableBaseError(f"{base} does not resolve against its remote: {output.reason(tool=argv[0])}")

        return int(output.stdout.strip())

    def catch_up(self, *, worktree: str, name: str, base: str) -> BranchCatchUp:
        self._fetch(worktree)
        for ref in (f"origin/{name}", f"origin/{base}"):
            if self._behind(worktree, ref):
                merging = self._merging(worktree, ref)
                if merging.outcome is BranchCatchUpOutcome.CONFLICTING:
                    return merging

        return BranchCatchUp.caught_up()

    def _behind(self, worktree: str, ref: str) -> bool:
        if not self._ref_exists(worktree, ref):
            return False

        argv = ["git", "-C", worktree, "rev-list", "--count", f"HEAD..{ref}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return int(output.stdout.strip()) > 0

    def _ref_exists(self, worktree: str, ref: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if output.code == 1:
            return False

        raise GitCommandFailedError.from_command(argv, output)

    def _merging(self, worktree: str, ref: str) -> BranchCatchUp:
        argv = ["git", "-C", worktree, "-c", "merge.ff=true", "-c", "commit.gpgsign=false", "merge", "--no-edit", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return BranchCatchUp.caught_up()
        if not self._merge_in_progress(worktree):
            raise GitCommandFailedError.from_command(argv, output)

        try:
            conflicting_paths = self._conflicting_paths(worktree)
        finally:
            self._abort_merge(worktree)

        return BranchCatchUp.conflicting(paths=conflicting_paths)

    def _conflicting_paths(self, worktree: str) -> tuple[str, ...]:
        argv = ["git", "-C", worktree, "-c", "core.quotePath=false", "diff", "--name-only", "--diff-filter=U"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return tuple(output.stdout.splitlines())

    def _merge_in_progress(self, worktree: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD"]
        output = self._process.run(argv, stdin="")

        return output.code == 0

    def _abort_merge(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "merge", "--abort"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

    def _fetch(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "fetch", "origin", "--quiet"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)
