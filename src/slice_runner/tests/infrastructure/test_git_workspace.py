from __future__ import annotations

import pytest

from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import Answer, AnsweringByArgv, ScriptedProcess
from slice_runner.tests.mothers.git_workspace_output_mother import GitWorkspaceOutputMother

_WORKTREE = "/repos/slice-runner"
_BRANCH = GitWorkspaceOutputMother.BRANCH
_TITLE = GitWorkspaceOutputMother.COMMIT_TITLE


class TestTheCommandsGitWorkspaceRuns:
    def test_staging_names_every_path_after_a_double_dash_and_never_asks_git_to_pick_them(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""), ProcessOutput(code=0, stdout="", stderr="")
        )

        GitWorkspace(process=process).stage(worktree=_WORKTREE, paths=("src/a.py", "src/tests/test_a.py"))

        assert process.calls[-1].argv == [
            "git",
            "-C",
            _WORKTREE,
            "add",
            "--",
            "src/a.py",
            "src/tests/test_a.py",
        ]
        for wildcard in ("-A", "--all", ".", "-u", "--update", ":/"):
            assert wildcard not in process.calls[-1].argv

    def test_it_asks_the_index_what_is_already_deleted_before_naming_the_paths_to_add(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""), ProcessOutput(code=0, stdout="", stderr="")
        )

        GitWorkspace(process=process).stage(worktree=_WORKTREE, paths=("src/a.py",))

        assert process.calls[0].argv == [
            "git",
            "-C",
            _WORKTREE,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=D",
        ]

    def test_the_index_is_read_against_head_so_it_is_what_the_commit_would_carry(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).staged(worktree=_WORKTREE)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "diff", "--cached", "--name-only"]

    def test_the_current_branch_comes_from_the_symbolic_ref_and_arrives_without_its_newline(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout=GitWorkspaceOutputMother.CURRENT_BRANCH_STDOUT, stderr="")
        )

        branch = GitWorkspace(process=process).current_branch(worktree=_WORKTREE)

        assert branch == _BRANCH
        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "symbolic-ref", "--short", "HEAD"]

    def test_committing_passes_the_message_as_one_argument_instead_of_letting_a_shell_split_it(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).commit(worktree=_WORKTREE, message=_TITLE)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "commit", "-m", _TITLE]

    def test_pushing_sets_the_upstream_so_the_branch_can_be_found_by_the_pull_request(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).push(worktree=_WORKTREE, branch=_BRANCH)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "push", "-u", "origin", _BRANCH]


class GitAnsweringTheWorkspace:
    @staticmethod
    def _git(*args: str) -> list[str]:
        return ["git", "-C", _WORKTREE, *args]

    @classmethod
    def _already_deleted(cls, stdout: str) -> Answer:
        return Answer.to_exactly(*cls._git("diff", "--cached", "--name-only", "--diff-filter=D"), stdout=stdout)

    @classmethod
    def _staged_names(cls, stdout: str) -> Answer:
        return Answer.to_exactly(*cls._git("diff", "--cached", "--name-only"), stdout=stdout)

    @staticmethod
    def _workspace(process: AnsweringByArgv) -> GitWorkspace:
        return GitWorkspace(process=process)


class TestWhatTheIndexReadsBack(GitAnsweringTheWorkspace):
    def test_what_it_staged_is_what_it_reads_back_deletions_included(self) -> None:
        process = AnsweringByArgv(
            self._already_deleted(GitWorkspaceOutputMother.NOTHING_LISTED),
            Answer.to_exactly(*self._git("add", "--", "added.py", "kept.py")),
            self._staged_names(GitWorkspaceOutputMother.ADDED_AND_DELETED_NAMES),
        )
        workspace = self._workspace(process)

        workspace.stage(worktree=_WORKTREE, paths=("added.py", "kept.py"))

        assert workspace.staged(worktree=_WORKTREE) == ("added.py", "kept.py")
        assert process.ran(*self._git("add", "--", "added.py", "kept.py"))

    def test_an_untouched_index_reads_back_empty_instead_of_one_blank_name(self) -> None:
        process = AnsweringByArgv(self._staged_names(GitWorkspaceOutputMother.NOTHING_LISTED))

        assert self._workspace(process).staged(worktree=_WORKTREE) == ()


class TestWhatStagingRefusesAndSkips(GitAnsweringTheWorkspace):
    def test_a_path_that_is_not_in_the_repo_raises_instead_of_staging_nothing_in_silence(self) -> None:
        process = AnsweringByArgv(
            self._already_deleted(GitWorkspaceOutputMother.NOTHING_LISTED),
            Answer.to_exactly(
                *self._git("add", "--", "never-written.py"),
                code=GitWorkspaceOutputMother.PATHSPEC_MATCHED_NOTHING_CODE,
                stderr=GitWorkspaceOutputMother.PATHSPEC_MATCHED_NOTHING_STDERR,
            ),
        )

        with pytest.raises(GitCommandFailedError, match="did not match any files"):
            self._workspace(process).stage(worktree=_WORKTREE, paths=("never-written.py",))

    def test_a_deletion_that_already_reached_the_index_does_not_abort_the_rest_of_the_round(self) -> None:
        process = AnsweringByArgv(
            self._already_deleted(GitWorkspaceOutputMother.DELETED_NAMES),
            Answer.to_exactly(*self._git("add", "--", "added.py")),
            self._staged_names(GitWorkspaceOutputMother.ADDED_AND_DELETED_NAMES),
        )
        workspace = self._workspace(process)

        workspace.stage(worktree=_WORKTREE, paths=("added.py", "kept.py"))

        assert process.times_invoked("add") == 1
        assert process.ran(*self._git("add", "--", "added.py"))
        assert workspace.staged(worktree=_WORKTREE) == ("added.py", "kept.py")

    def test_a_round_whose_every_path_is_an_already_staged_deletion_stages_without_calling_git_add(self) -> None:
        process = AnsweringByArgv(
            self._already_deleted(GitWorkspaceOutputMother.DELETED_NAMES),
            self._staged_names(GitWorkspaceOutputMother.DELETED_NAMES),
        )
        workspace = self._workspace(process)

        workspace.stage(worktree=_WORKTREE, paths=("kept.py",))

        assert not process.invoked("add")
        assert workspace.staged(worktree=_WORKTREE) == ("kept.py",)


class TestWhatTheBranchIsTold(GitAnsweringTheWorkspace):
    def test_the_branch_a_repo_is_on_is_the_one_it_reports(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("symbolic-ref", "--short", "HEAD"), stdout=GitWorkspaceOutputMother.CURRENT_BRANCH_STDOUT
            )
        )

        assert self._workspace(process).current_branch(worktree=_WORKTREE) == _BRANCH

    def test_a_detached_head_raises_instead_of_reporting_a_branch_name_nobody_is_on(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("symbolic-ref", "--short", "HEAD"),
                code=GitWorkspaceOutputMother.DETACHED_HEAD_CODE,
                stderr=GitWorkspaceOutputMother.DETACHED_HEAD_STDERR,
            )
        )

        with pytest.raises(GitCommandFailedError, match="not a symbolic ref"):
            self._workspace(process).current_branch(worktree=_WORKTREE)


class TestWhatCommittingAndPushingTell(GitAnsweringTheWorkspace):
    def test_a_commit_git_accepts_returns_without_reading_its_summary_as_a_failure(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("commit", "-m", _TITLE), stdout=GitWorkspaceOutputMother.ACCEPTED_COMMIT_STDOUT
            )
        )

        self._workspace(process).commit(worktree=_WORKTREE, message=_TITLE)

        assert process.ran(*self._git("commit", "-m", _TITLE))

    def test_nothing_to_commit_raises_instead_of_passing_for_a_commit_that_never_happened(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("commit", "-m", _TITLE),
                code=GitWorkspaceOutputMother.NOTHING_TO_COMMIT_CODE,
                stdout=GitWorkspaceOutputMother.NOTHING_TO_COMMIT_STDOUT,
            )
        )

        with pytest.raises(GitCommandFailedError, match="nothing to commit"):
            self._workspace(process).commit(worktree=_WORKTREE, message=_TITLE)

    def test_a_push_git_accepts_returns_without_reading_its_progress_as_a_failure(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("push", "-u", "origin", _BRANCH), stderr=GitWorkspaceOutputMother.ACCEPTED_PUSH_STDERR
            )
        )

        self._workspace(process).push(worktree=_WORKTREE, branch=_BRANCH)

        assert process.ran(*self._git("push", "-u", "origin", _BRANCH))

    def test_a_push_with_no_remote_to_push_to_raises_with_the_reason_git_gave(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._git("push", "-u", "origin", _BRANCH),
                code=GitWorkspaceOutputMother.NO_REMOTE_CODE,
                stderr=GitWorkspaceOutputMother.NO_REMOTE_STDERR,
            )
        )

        with pytest.raises(GitCommandFailedError, match="origin"):
            self._workspace(process).push(worktree=_WORKTREE, branch=_BRANCH)
