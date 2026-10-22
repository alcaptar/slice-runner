from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.listed_worktree import ListedWorktree


class Worktrees(ABC):
    @abstractmethod
    def listed(self, *, root: str) -> tuple[ListedWorktree, ...]: ...

    @abstractmethod
    def branch_exists(self, *, root: str, name: str) -> bool: ...

    @abstractmethod
    def common_dir(self, *, path: str) -> str: ...

    @abstractmethod
    def add_new_branch(self, *, root: str, path: str, branch: str, base: str) -> None: ...

    @abstractmethod
    def add_on_branch(self, *, root: str, path: str, branch: str) -> None: ...

    @abstractmethod
    def prune(self, *, root: str) -> None: ...

    @abstractmethod
    def is_mounted(self, *, root: str, path: str, branch: str) -> bool: ...

    @abstractmethod
    def has_uncommitted_work(self, *, path: str) -> bool: ...

    @abstractmethod
    def local_only_commits(self, *, root: str, branch: str) -> int: ...

    @abstractmethod
    def remove(self, *, root: str, path: str) -> None: ...

    @abstractmethod
    def delete_branch(self, *, root: str, branch: str) -> None: ...

    @abstractmethod
    def exclude(self, *, root: str, rule: str) -> None: ...
