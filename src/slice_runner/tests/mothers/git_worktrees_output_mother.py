from __future__ import annotations

from typing import ClassVar


class GitWorktreesOutputMother:
    SHA: ClassVar[str] = "3f2a9c1d5e7b84a06c91d2f8b3a7e4c5d6f01a2b"

    @classmethod
    def listing(cls, *blocks: str) -> str:
        return "".join(f"{block}\n" for block in blocks)

    @classmethod
    def main_clone(cls, *, path: str, branch: str) -> str:
        return f"worktree {path}\nHEAD {cls.SHA}\nbranch refs/heads/{branch}\n"

    @classmethod
    def mounted(cls, *, path: str, branch: str) -> str:
        return f"worktree {path}\nHEAD {cls.SHA}\nbranch refs/heads/{branch}\n"

    @classmethod
    def detached(cls, *, path: str) -> str:
        return f"worktree {path}\nHEAD {cls.SHA}\ndetached\n"

    @classmethod
    def whose_directory_was_deleted(cls, *, path: str, branch: str) -> str:
        return (
            f"worktree {path}\nHEAD {cls.SHA}\nbranch refs/heads/{branch}\n"
            "prunable gitdir file points to non-existent location\n"
        )

    @classmethod
    def verified_ref(cls) -> str:
        return f"{cls.SHA}\n"

    @staticmethod
    def not_a_repository() -> str:
        return "fatal: not a git repository (or any of the parent directories): .git\n"

    @staticmethod
    def absolute_git_directory(path: str) -> str:
        return f"{path}\n"

    @staticmethod
    def branch_already_exists(branch: str) -> str:
        return f"fatal: a branch named '{branch}' already exists\n"

    @staticmethod
    def path_already_exists(path: str) -> str:
        return f"fatal: '{path}' already exists\n"

    @staticmethod
    def clean_status() -> str:
        return ""

    @staticmethod
    def status_with_a_modified_tracked_file(path: str) -> str:
        return f" M {path}\n"

    @staticmethod
    def status_with_an_untracked_file(path: str) -> str:
        return f"?? {path}\n"

    @staticmethod
    def status_with_a_staged_file(path: str) -> str:
        return f"A  {path}\n"

    @staticmethod
    def cannot_change_to_a_missing_directory(path: str) -> str:
        return f"fatal: cannot change to '{path}': No such file or directory\n"

    @staticmethod
    def commit_count(count: int) -> str:
        return f"{count}\n"

    @staticmethod
    def unknown_branch(branch: str) -> str:
        return (
            f"fatal: ambiguous argument 'refs/heads/{branch}': unknown revision or path not in the working tree.\n"
            "Use '--' to separate paths from revisions, like this:\n"
            "'git <command> [<revision>...] -- [<file>...]'\n"
        )

    @staticmethod
    def removal_refused_for_uncommitted_work(path: str) -> str:
        return f"fatal: '{path}' contains modified or untracked files, use --force to delete it\n"

    @staticmethod
    def branch_not_found(branch: str) -> str:
        return f"error: branch '{branch}' not found.\n"
