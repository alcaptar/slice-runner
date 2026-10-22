from __future__ import annotations

from typing import ClassVar


class GitBranchesOutputMother:
    SHA: ClassVar[str] = "3f2a9c1d5e7b84a06c91d2f8b3a7e4c5d6f01a2b"

    @staticmethod
    def commit_count(count: int) -> str:
        return f"{count}\n"

    @classmethod
    def verified_ref(cls) -> str:
        return f"{cls.SHA}\n"

    @staticmethod
    def fetch_from_a_clone_with_no_origin() -> str:
        return (
            "fatal: 'origin' does not appear to be a git repository\n"
            "fatal: Could not read from remote repository.\n"
            "\n"
            "Please make sure you have the correct access rights\n"
            "and the repository exists.\n"
        )

    @staticmethod
    def base_that_does_not_resolve(base: str) -> str:
        return (
            f"fatal: ambiguous argument '{base}..origin/{base}': unknown revision or path not in the working tree.\n"
            "Use '--' to separate paths from revisions, like this:\n"
            "'git <command> [<revision>...] -- [<file>...]'\n"
        )

    @staticmethod
    def fast_forward() -> str:
        return (
            "Updating 3f2a9c1..8b1d4e7\n"
            "Fast-forward\n"
            " pushed-from-elsewhere.txt | 1 +\n"
            " 1 file changed, 1 insertion(+)\n"
        )

    @staticmethod
    def merge_commit() -> str:
        return "Merge made by the 'ort' strategy.\n pushed-from-elsewhere.txt | 1 +\n 1 file changed, 1 insertion(+)\n"

    @staticmethod
    def conflict_on_shared_file() -> str:
        return (
            "Auto-merging shared.txt\n"
            "CONFLICT (content): Merge conflict in shared.txt\n"
            "Automatic merge failed; fix conflicts and then commit the result.\n"
        )

    @staticmethod
    def local_changes_overwritten_by_merge() -> str:
        return (
            "error: Your local changes to the following files would be overwritten by merge:\n"
            "\tshared.txt\n"
            "Please commit your changes or stash them before you merge.\n"
            "Aborting\n"
        )

    @staticmethod
    def unmerged(*paths: str) -> str:
        return "".join(f"{path}\n" for path in paths)
