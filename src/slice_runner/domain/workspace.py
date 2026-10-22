from __future__ import annotations

from abc import ABC, abstractmethod


class Workspace(ABC):
    @abstractmethod
    def stage(self, *, worktree: str, paths: tuple[str, ...]) -> None: ...

    @abstractmethod
    def staged(self, *, worktree: str) -> tuple[str, ...]: ...

    @abstractmethod
    def current_branch(self, *, worktree: str) -> str: ...

    @abstractmethod
    def commit(self, *, worktree: str, message: str) -> None: ...

    @abstractmethod
    def push(self, *, worktree: str, branch: str) -> None: ...
