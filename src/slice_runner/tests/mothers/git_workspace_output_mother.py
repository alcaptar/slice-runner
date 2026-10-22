from __future__ import annotations

from typing import ClassVar


class GitWorkspaceOutputMother:
    BRANCH: ClassVar[str] = "slice/08-entrega-de-la-slice"
    CURRENT_BRANCH_STDOUT: ClassVar[str] = f"{BRANCH}\n"

    NOTHING_LISTED: ClassVar[str] = ""
    ADDED_AND_DELETED_NAMES: ClassVar[str] = "added.py\nkept.py\n"
    DELETED_NAMES: ClassVar[str] = "kept.py\n"

    PATHSPEC_MATCHED_NOTHING_STDERR: ClassVar[str] = "fatal: pathspec 'never-written.py' did not match any files\n"
    PATHSPEC_MATCHED_NOTHING_CODE: ClassVar[int] = 128

    DETACHED_HEAD_STDERR: ClassVar[str] = "fatal: ref HEAD is not a symbolic ref\n"
    DETACHED_HEAD_CODE: ClassVar[int] = 128

    NOTHING_TO_COMMIT_STDOUT: ClassVar[str] = f"On branch {BRANCH}\nnothing to commit, working tree clean\n"
    NOTHING_TO_COMMIT_CODE: ClassVar[int] = 1

    COMMIT_TITLE: ClassVar[str] = "feat(entrega-de-la-slice): commitear solo lo juzgado y abrir la pull request"

    ACCEPTED_COMMIT_STDOUT: ClassVar[str] = (
        f"[{BRANCH} 3f2a9c1] {COMMIT_TITLE}\n 2 files changed, 3 insertions(+), 1 deletion(-)\n"
    )

    ACCEPTED_PUSH_STDERR: ClassVar[str] = (
        "To ../remote.git\n"
        f" * [new branch]      {BRANCH} -> {BRANCH}\n"
        f"branch '{BRANCH}' set up to track 'origin/{BRANCH}'.\n"
    )

    NO_REMOTE_STDERR: ClassVar[str] = (
        "fatal: 'origin' does not appear to be a git repository\n"
        "fatal: Could not read from remote repository.\n"
        "\n"
        "Please make sure you have the correct access rights\n"
        "and the repository exists.\n"
    )
    NO_REMOTE_CODE: ClassVar[int] = 128
