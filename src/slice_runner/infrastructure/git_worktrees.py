from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.listed_worktree import ListedWorktree
from slice_runner.domain.worktrees import Worktrees
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitWorktrees(Worktrees):
    BRANCH_PREFIX: ClassVar[str] = "refs/heads/"
    EXCLUDE_FILE: ClassVar[tuple[str, str]] = ("info", "exclude")
    NOT_A_REPOSITORY: ClassVar[int] = 128

    def __init__(self, *, process: Process) -> None:
        self._process = process

    def listed(self, *, root: str) -> tuple[ListedWorktree, ...]:
        output = self._git(root, "worktree", "list", "--porcelain")
        entries = [block.splitlines() for block in output.split("\n\n") if block.strip()]

        return tuple(self._entry(lines, main=index == 0) for index, lines in enumerate(entries))

    def branch_exists(self, *, root: str, name: str) -> bool:
        argv = ["git", "-C", root, "rev-parse", "--verify", "--quiet", f"{self.BRANCH_PREFIX}{name}"]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if output.code == 1:
            return False

        raise GitCommandFailedError.from_command(argv, output)

    def common_dir(self, *, path: str) -> str:
        output = self._process.run(self._common_dir_argv(path), stdin="")
        if output.code == 0:
            return output.stdout.strip()
        if output.code == self.NOT_A_REPOSITORY:
            return ""

        raise GitCommandFailedError.from_command(self._common_dir_argv(path), output)

    def add_new_branch(self, *, root: str, path: str, branch: str, base: str) -> None:
        self._git(root, "fetch", "origin", "--quiet")
        self._git(root, "worktree", "add", "-b", branch, path, f"origin/{base}")

    def add_on_branch(self, *, root: str, path: str, branch: str) -> None:
        self._git(root, "worktree", "add", path, branch)

    def prune(self, *, root: str) -> None:
        self._git(root, "worktree", "prune")

    def is_mounted(self, *, root: str, path: str, branch: str) -> bool:
        listing = self._asked(root, "worktree", "list", "--porcelain")
        entries = [block.splitlines() for block in listing.split("\n\n") if block.strip()]
        sought = Path(path).resolve()

        return any(
            Path(entry.path).resolve() == sought and entry.branch == branch
            for entry in (self._entry(lines, main=False) for lines in entries)
        )

    def has_uncommitted_work(self, *, path: str) -> bool:
        return self._asked(path, "status", "--porcelain").strip() != ""

    def local_only_commits(self, *, root: str, branch: str) -> int:
        counted = self._asked(root, "rev-list", "--count", f"{self.BRANCH_PREFIX}{branch}", "--not", "--remotes")
        try:
            return int(counted.strip())
        except ValueError as unreadable:
            raise WorktreeRetirementError(
                f"git rev-list --count answered {counted!r}, which is no number"
            ) from unreadable

    def remove(self, *, root: str, path: str) -> None:
        self._asked(root, "worktree", "remove", path)

    def delete_branch(self, *, root: str, branch: str) -> None:
        self._asked(root, "branch", "-D", branch)

    def exclude(self, *, root: str, rule: str) -> None:
        common = self.common_dir(path=root)
        if common == "":
            raise GitCommandFailedError(f"{root} is not inside a git repository, so there is no exclusion to write")
        exclusion = Path(common, *self.EXCLUDE_FILE)
        exclusion.parent.mkdir(parents=True, exist_ok=True)
        present = exclusion.read_text().splitlines() if exclusion.exists() else []
        if rule in present:
            return
        separator = "\n" if present and not exclusion.read_text().endswith("\n") else ""
        with exclusion.open("a") as stream:
            stream.write(f"{separator}{rule}\n")

    def _entry(self, lines: list[str], *, main: bool) -> ListedWorktree:
        path = ""
        branch = ""
        prunable = False
        for line in lines:
            key, _, value = line.partition(" ")
            if key == "worktree":
                path = value
            elif key == "branch":
                branch = value.removeprefix(self.BRANCH_PREFIX)
            elif key == "prunable":
                prunable = True

        return ListedWorktree(path=path, branch=branch, prunable=prunable, main=main)

    @staticmethod
    def _common_dir_argv(path: str) -> list[str]:
        return ["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"]

    def _asked(self, root: str, *args: str) -> str:
        try:
            return self._git(root, *args)
        except (GitCommandFailedError, ProcessTimedOutError, ProcessNotRunnableError) as failed:
            raise WorktreeRetirementError(str(failed)) from failed

    def _git(self, root: str, *args: str) -> str:
        argv = ["git", "-C", root, *args]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return output.stdout
