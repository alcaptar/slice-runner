from __future__ import annotations

from typing import ClassVar


class GitDiffOutputMother:
    WORKTREE: ClassVar[str] = "/repos/slice-runner"
    BASE: ClassVar[str] = "master"
    REMOTE_BASE: ClassVar[str] = "origin/master"

    _EDITED_MODULE_PATCH: ClassVar[str] = (
        "diff --git a/mod.py b/mod.py\n"
        "index 8ae4551..cfb8bd4 100644\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def f() -> int:\n"
        "-    return 1\n"
        "+    return 2\n"
    )
    _ADDED_OTHER_PATCH: ClassVar[str] = (
        "diff --git a/other.py b/other.py\n"
        "new file mode 100644\n"
        "index 0000000..5e1c309\n"
        "--- /dev/null\n"
        "+++ b/other.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def g() -> int:\n"
        "+    return 3\n"
    )
    _BINARY_ASSET_PATCH: ClassVar[str] = (
        "diff --git a/asset.png b/asset.png\n"
        "index 3c1f0a2..9d4b7e8 100644\n"
        "Binary files a/asset.png and b/asset.png differ\n"
    )
    _ADDED_FIRST_PATCH: ClassVar[str] = (
        "diff --git a/first.py b/first.py\n"
        "new file mode 100644\n"
        "index 0000000..a41d7c0\n"
        "--- /dev/null\n"
        "+++ b/first.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def one() -> int:\n"
        "+    return 1\n"
    )
    _ADDED_SECOND_PATCH: ClassVar[str] = (
        "diff --git a/second.py b/second.py\n"
        "new file mode 100644\n"
        "index 0000000..c92be15\n"
        "--- /dev/null\n"
        "+++ b/second.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+def two() -> int:\n"
        "+    return 2\n"
    )
    _ADDED_UPSTREAM_PATCH: ClassVar[str] = (
        "diff --git a/upstream.py b/upstream.py\n"
        "new file mode 100644\n"
        "index 0000000..7d03f6a\n"
        "--- /dev/null\n"
        "+++ b/upstream.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def a() -> int:\n"
        "+    return 4\n"
        "+\n"
    )

    EDITED_MODULE_TEXT: ClassVar[str] = _EDITED_MODULE_PATCH
    EDITED_MODULE_NAMES: ClassVar[str] = "mod.py\n"
    EDITED_MODULE_NUMSTAT: ClassVar[str] = "1\t1\tmod.py\n"

    EDITED_AND_ADDED_MODULE_NAMES: ClassVar[str] = "mod.py\nother.py\n"
    EDITED_AND_ADDED_MODULE_NUMSTAT: ClassVar[str] = "1\t1\tmod.py\n2\t0\tother.py\n"
    EDITED_AND_ADDED_MODULE_TEXT: ClassVar[str] = _EDITED_MODULE_PATCH + _ADDED_OTHER_PATCH

    EDITED_MODULE_AND_BINARY_NAMES: ClassVar[str] = "asset.png\nmod.py\n"
    EDITED_MODULE_AND_BINARY_NUMSTAT: ClassVar[str] = "-\t-\tasset.png\n1\t1\tmod.py\n"
    EDITED_MODULE_AND_BINARY_TEXT: ClassVar[str] = _BINARY_ASSET_PATCH + _EDITED_MODULE_PATCH

    TWO_ROUNDS_NAMES: ClassVar[str] = "first.py\nsecond.py\n"
    TWO_ROUNDS_NUMSTAT: ClassVar[str] = "2\t0\tfirst.py\n2\t0\tsecond.py\n"
    TWO_ROUNDS_TEXT: ClassVar[str] = _ADDED_FIRST_PATCH + _ADDED_SECOND_PATCH

    EDITED_MODULE_AND_UPSTREAM_NAMES: ClassVar[str] = "mod.py\nupstream.py\n"
    EDITED_MODULE_AND_UPSTREAM_NUMSTAT: ClassVar[str] = "1\t1\tmod.py\n3\t0\tupstream.py\n"
    EDITED_MODULE_AND_UPSTREAM_TEXT: ClassVar[str] = _EDITED_MODULE_PATCH + _ADDED_UPSTREAM_PATCH

    NOTHING_STAGED: ClassVar[str] = ""

    UNKNOWN_BASE_STDERR: ClassVar[str] = (
        "fatal: ambiguous argument 'not-a-base': unknown revision or path not in the working tree.\n"
        "Use '--' to separate paths from revisions, like this:\n"
        "'git <command> [<revision>...] -- [<file>...]'\n"
    )
    UNKNOWN_BASE_CODE: ClassVar[int] = 128

    NOT_A_REPO_DIFF_STDERR: ClassVar[str] = (
        "error: unknown option `cached'\nusage: git diff --no-index [<options>] <path> <path> [<pathspec>...]\n"
    )
    NOT_A_REPO_DIFF_CODE: ClassVar[int] = 129

    NOT_A_REPO_STATUS_STDERR: ClassVar[str] = "fatal: not a git repository (or any of the parent directories): .git\n"
    NOT_A_REPO_STATUS_CODE: ClassVar[int] = 128

    CLEAN_STATUS: ClassVar[str] = ""
    EDITED_NOT_STAGED_STATUS: ClassVar[str] = " M mod.py\n"
    DELETED_NOT_STAGED_STATUS: ClassVar[str] = " D mod.py\n"
    STAGED_AND_UNTOUCHED_STATUS: ClassVar[str] = "M  mod.py\n"
    STAGED_AND_TOUCHED_AGAIN_STATUS: ClassVar[str] = "MM mod.py\n"
    UNTRACKED_INSIDE_NEW_DIRECTORY_STATUS: ClassVar[str] = "?? new_module/leftover.py\n"
