from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.listed_worktree import ListedWorktree


class ListedWorktreeMother:
    ROOT: ClassVar[str] = "/repos/slice-runner"
    BASE: ClassVar[str] = "master"

    @classmethod
    def main_clone(cls, *, on: str = BASE) -> ListedWorktree:
        return ListedWorktree(path=cls.ROOT, branch=on, prunable=False, main=True)

    @staticmethod
    def mounted(*, path: str, branch: str) -> ListedWorktree:
        return ListedWorktree(path=path, branch=branch, prunable=False, main=False)

    @staticmethod
    def whose_directory_was_deleted(*, path: str, branch: str) -> ListedWorktree:
        return ListedWorktree(path=path, branch=branch, prunable=True, main=False)

    @staticmethod
    def detached(*, path: str) -> ListedWorktree:
        return ListedWorktree(path=path, branch="", prunable=False, main=False)
