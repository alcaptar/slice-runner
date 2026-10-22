from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.git_diff_reader import GitDiffReader
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.git_diff_output_mother import GitDiffOutputMother

if TYPE_CHECKING:
    from slice_runner.domain.slice_diff import SliceDiff


class TheCommandsTheReaderAsksGit:
    @staticmethod
    def _names_argv(base: str) -> list[str]:
        return ["git", "-C", GitDiffOutputMother.WORKTREE, "diff", "--cached", "--name-only", "--merge-base", base]

    @staticmethod
    def _numstat_argv(base: str) -> list[str]:
        return ["git", "-C", GitDiffOutputMother.WORKTREE, "diff", "--cached", "--numstat", "--merge-base", base]

    @staticmethod
    def _text_argv(base: str) -> list[str]:
        return ["git", "-C", GitDiffOutputMother.WORKTREE, "diff", "--cached", "--merge-base", base]

    @staticmethod
    def _status_argv() -> list[str]:
        return ["git", "-C", GitDiffOutputMother.WORKTREE, "status", "--porcelain", "--untracked-files=all"]

    @classmethod
    def _git_staging(cls, *, names: str, numstat: str, text: str, base: str) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer.to_exactly(*cls._names_argv(base), stdout=names),
            Answer.to_exactly(*cls._text_argv(base), stdout=text),
            Answer.to_exactly(*cls._numstat_argv(base), stdout=numstat),
        )

    @staticmethod
    def _read(process: AnsweringByArgv, *, base: str = GitDiffOutputMother.BASE) -> SliceDiff:
        return GitDiffReader(process=process).read(worktree=GitDiffOutputMother.WORKTREE, base=base)

    @staticmethod
    def _dirty(process: AnsweringByArgv) -> tuple[str, ...]:
        return GitDiffReader(process=process).dirty(worktree=GitDiffOutputMother.WORKTREE)

    @classmethod
    def _git_reporting_status(cls, stdout: str) -> AnsweringByArgv:
        return AnsweringByArgv(Answer.to_exactly(*cls._status_argv(), stdout=stdout))


class TestWhatItReads(TheCommandsTheReaderAsksGit):
    def test_the_diff_comes_back_as_text_so_nobody_downstream_has_to_open_a_file(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert read.text == GitDiffOutputMother.EDITED_MODULE_TEXT

    def test_reading_the_diff_runs_only_the_three_diff_commands_so_it_leaves_no_file_and_no_staging_behind(
        self,
    ) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert read.files == ("mod.py",)
        assert read.text == GitDiffOutputMother.EDITED_MODULE_TEXT
        assert sorted(call.argv for call in process.calls) == sorted(
            [
                self._names_argv(GitDiffOutputMother.BASE),
                self._text_argv(GitDiffOutputMother.BASE),
                self._numstat_argv(GitDiffOutputMother.BASE),
            ]
        )
        assert not any("--output" in call.argv or "add" in call.argv for call in process.calls)

    def test_the_scope_is_every_staged_file_and_not_a_path_to_a_listing(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert read.files == ("mod.py", "other.py")

    def test_the_stats_count_the_one_file_touched_and_its_added_and_deleted_lines(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (1, 1, 1)

    def test_a_second_file_staged_is_counted_into_the_same_stats(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_AND_ADDED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 3, 1)

    def test_a_binary_file_staged_is_counted_as_a_file_changed_with_no_lines_because_git_reports_none(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_AND_BINARY_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_AND_BINARY_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_AND_BINARY_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 1, 1)

    def test_a_round_already_committed_still_reaches_the_diff_because_it_is_taken_from_the_merge_base(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.TWO_ROUNDS_NAMES,
            numstat=GitDiffOutputMother.TWO_ROUNDS_NUMSTAT,
            text=GitDiffOutputMother.TWO_ROUNDS_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert read.files == ("first.py", "second.py")
        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 4, 0)
        assert process.ran(*self._names_argv(GitDiffOutputMother.BASE))


class TestDiffingAgainstTheBranchesActualOrigin(TheCommandsTheReaderAsksGit):
    def test_the_base_it_is_given_reaches_git_untouched_so_the_remote_the_branch_came_from_can_be_the_base(
        self,
    ) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_TEXT,
            base=GitDiffOutputMother.REMOTE_BASE,
        )

        read = self._read(process, base=GitDiffOutputMother.REMOTE_BASE)

        assert read.files == ("mod.py",)
        assert all(call.argv[-1] == GitDiffOutputMother.REMOTE_BASE for call in process.calls)

    def test_a_stale_local_base_is_not_swapped_for_the_remote_one_so_what_only_lived_on_the_remote_leaks(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_AND_UPSTREAM_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_AND_UPSTREAM_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_AND_UPSTREAM_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process, base=GitDiffOutputMother.BASE)

        assert read.files == ("mod.py", "upstream.py")
        assert (read.stats.files_changed, read.stats.lines_added, read.stats.lines_deleted) == (2, 4, 1)
        assert not process.invoked(GitDiffOutputMother.REMOTE_BASE)


class TestWhatItRefusesToRead(TheCommandsTheReaderAsksGit):
    def test_an_unstaged_change_is_not_in_the_diff_because_every_read_is_of_the_index(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.EDITED_MODULE_NAMES,
            numstat=GitDiffOutputMother.EDITED_MODULE_NUMSTAT,
            text=GitDiffOutputMother.EDITED_MODULE_TEXT,
            base=GitDiffOutputMother.BASE,
        )

        read = self._read(process)

        assert read.text == GitDiffOutputMother.EDITED_MODULE_TEXT
        assert all("--cached" in call.argv for call in process.calls)

    def test_nothing_staged_is_an_empty_index_and_not_an_empty_diff(self) -> None:
        process = self._git_staging(
            names=GitDiffOutputMother.NOTHING_STAGED,
            numstat=GitDiffOutputMother.NOTHING_STAGED,
            text=GitDiffOutputMother.NOTHING_STAGED,
            base=GitDiffOutputMother.BASE,
        )

        with pytest.raises(EmptyIndexError, match="nothing staged"):
            self._read(process)

    def test_a_base_that_does_not_resolve_is_told_apart_from_an_empty_index(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._names_argv("not-a-base"),
                code=GitDiffOutputMother.UNKNOWN_BASE_CODE,
                stderr=GitDiffOutputMother.UNKNOWN_BASE_STDERR,
            )
        )

        with pytest.raises(UnresolvableRepoOrBaseError, match="not-a-base"):
            self._read(process, base="not-a-base")

    def test_a_directory_that_is_not_a_repo_is_told_apart_too(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._names_argv(GitDiffOutputMother.BASE),
                code=GitDiffOutputMother.NOT_A_REPO_DIFF_CODE,
                stderr=GitDiffOutputMother.NOT_A_REPO_DIFF_STDERR,
            )
        )

        with pytest.raises(UnresolvableRepoOrBaseError, match="unknown option"):
            self._read(process)


class TestWhatDirtyReports(TheCommandsTheReaderAsksGit):
    def test_a_tracked_file_edited_without_staging_is_named(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.EDITED_NOT_STAGED_STATUS)

        assert self._dirty(process) == ("mod.py",)

    def test_a_tracked_file_deleted_without_staging_is_named(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.DELETED_NOT_STAGED_STATUS)

        assert self._dirty(process) == ("mod.py",)

    def test_a_clean_worktree_reports_no_file_at_all(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.CLEAN_STATUS)

        assert self._dirty(process) == ()

    def test_a_change_staged_and_not_touched_again_is_not_named_because_it_was_already_declared(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.STAGED_AND_UNTOUCHED_STATUS)

        assert self._dirty(process) == ()

    def test_a_change_staged_and_then_touched_again_is_still_named_for_the_part_left_undeclared(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.STAGED_AND_TOUCHED_AGAIN_STATUS)

        assert self._dirty(process) == ("mod.py",)

    def test_an_untracked_file_inside_a_new_directory_is_named_by_itself_not_collapsed_to_its_directory(self) -> None:
        process = self._git_reporting_status(GitDiffOutputMother.UNTRACKED_INSIDE_NEW_DIRECTORY_STATUS)

        assert self._dirty(process) == ("new_module/leftover.py",)


class TestWhatDirtyRefusesToRead(TheCommandsTheReaderAsksGit):
    def test_a_directory_that_is_not_a_repo_raises_the_exception_the_repos_git_commands_share(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self._status_argv(),
                code=GitDiffOutputMother.NOT_A_REPO_STATUS_CODE,
                stderr=GitDiffOutputMother.NOT_A_REPO_STATUS_STDERR,
            )
        )

        with pytest.raises(GitCommandFailedError, match="not a git repository"):
            self._dirty(process)
