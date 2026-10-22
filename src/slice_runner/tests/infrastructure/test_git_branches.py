from __future__ import annotations

from typing import ClassVar

import pytest

from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.infrastructure.git_branches import GitBranches
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.process import ProcessOutput, ProcessTimedOutError
from slice_runner.tests.doubles import Answer, AnsweringByArgv, AnsweringByArgvRaisingOn, ScriptedProcess
from slice_runner.tests.mothers.branch_catch_up_mother import BranchCatchUpMother
from slice_runner.tests.mothers.git_branches_output_mother import GitBranchesOutputMother


class BranchesCommands:
    WORKTREE: ClassVar[str] = "/repos/slice-runner"
    BASE: ClassVar[str] = "master"
    SLICE_BRANCH: ClassVar[str] = "slice/22-la-rama-se-pone-al-dia"

    @classmethod
    def fetch(cls) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "fetch", "origin", "--quiet")

    @classmethod
    def commits_behind_remote(cls, base: str) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "rev-list", "--count", f"{base}..origin/{base}")

    @classmethod
    def ref_exists(cls, ref: str) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "rev-parse", "--verify", "--quiet", ref)

    @classmethod
    def commits_behind(cls, ref: str) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "rev-list", "--count", f"HEAD..{ref}")

    @classmethod
    def merge(cls, ref: str) -> tuple[str, ...]:
        return (
            "git",
            "-C",
            cls.WORKTREE,
            "-c",
            "merge.ff=true",
            "-c",
            "commit.gpgsign=false",
            "merge",
            "--no-edit",
            ref,
        )

    @classmethod
    def merge_head(cls) -> tuple[str, ...]:
        return cls.ref_exists("MERGE_HEAD")

    @classmethod
    def unmerged_paths(cls) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "-c", "core.quotePath=false", "diff", "--name-only", "--diff-filter=U")

    @classmethod
    def abort_merge(cls) -> tuple[str, ...]:
        return ("git", "-C", cls.WORKTREE, "merge", "--abort")

    @classmethod
    def fetched(cls) -> Answer:
        return Answer.to_exactly(*cls.fetch())

    @classmethod
    def present(cls, ref: str) -> Answer:
        return Answer.to_exactly(*cls.ref_exists(ref), stdout=GitBranchesOutputMother.verified_ref())

    @classmethod
    def absent(cls, ref: str) -> Answer:
        return Answer.to_exactly(*cls.ref_exists(ref), code=1)

    @classmethod
    def behind(cls, ref: str, *, by: int) -> Answer:
        return Answer.to_exactly(*cls.commits_behind(ref), stdout=GitBranchesOutputMother.commit_count(by))

    @classmethod
    def merged(cls, ref: str) -> Answer:
        return Answer.to_exactly(*cls.merge(ref), stdout=GitBranchesOutputMother.merge_commit())

    @classmethod
    def stopped_by_a_conflict(cls, ref: str) -> Answer:
        return Answer.to_exactly(*cls.merge(ref), code=1, stdout=GitBranchesOutputMother.conflict_on_shared_file())

    @classmethod
    def merge_in_progress(cls) -> Answer:
        return Answer.to_exactly(*cls.merge_head(), stdout=GitBranchesOutputMother.verified_ref())

    @classmethod
    def aborted(cls) -> Answer:
        return Answer.to_exactly(*cls.abort_merge())

    @classmethod
    def catching_up(cls, process: AnsweringByArgv) -> BranchCatchUp:
        return GitBranches(process=process).catch_up(worktree=cls.WORKTREE, name=cls.SLICE_BRANCH, base=cls.BASE)

    @classmethod
    def remote_slice_branch(cls) -> str:
        return f"origin/{cls.SLICE_BRANCH}"

    @classmethod
    def remote_base(cls) -> str:
        return f"origin/{cls.BASE}"

    @classmethod
    def merge_calls_of(cls, process: AnsweringByArgv) -> list[list[str]]:
        return [call.argv for call in process.calls if "merge" in call.argv and "--no-edit" in call.argv]


class TestCommitsBehindRemoteWithTheReasonOnlyOnStdout:
    def test_the_message_carries_what_stdout_says_instead_of_the_bare_exit_code(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=1, stdout="fatal: ambiguous argument 'main..origin/main'", stderr=""),
        )

        with pytest.raises(UnresolvableBaseError, match="fatal: ambiguous argument"):
            GitBranches(process=process).commits_behind_remote(worktree="/repos/slice-runner", base="main")


class TestGitBranchesComparingABaseAgainstItsRemote(BranchesCommands):
    def _comparing(self, process: AnsweringByArgv, *, base: str | None = None) -> int:
        return GitBranches(process=process).commits_behind_remote(worktree=self.WORKTREE, base=base or self.BASE)

    def test_a_base_whose_remote_has_no_commit_it_lacks_reports_zero_commits_behind(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.commits_behind_remote(self.BASE), stdout=GitBranchesOutputMother.commit_count(0)),
        )

        assert self._comparing(process) == 0

    def test_a_base_whose_remote_has_commits_it_lacks_reports_how_many(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.commits_behind_remote(self.BASE), stdout=GitBranchesOutputMother.commit_count(3)),
        )

        assert self._comparing(process) == 3

    def test_comparing_the_base_fetches_first_so_a_push_nobody_fetched_by_hand_is_still_seen(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.commits_behind_remote(self.BASE), stdout=GitBranchesOutputMother.commit_count(1)),
        )

        self._comparing(process)

        assert [call.argv for call in process.calls] == [
            list(self.fetch()),
            list(self.commits_behind_remote(self.BASE)),
        ]

    def test_comparing_the_base_only_fetches_and_counts_so_the_local_branch_is_never_moved(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.commits_behind_remote(self.BASE), stdout=GitBranchesOutputMother.commit_count(1)),
        )

        self._comparing(process)

        assert not any(process.invoked(token) for token in ("pull", "merge", "reset", "checkout", "update-ref"))

    def test_a_worktree_with_no_remote_to_fetch_from_raises_with_the_reason_git_gave(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.fetch(), code=128, stderr=GitBranchesOutputMother.fetch_from_a_clone_with_no_origin()
            )
        )

        with pytest.raises(GitCommandFailedError, match="'origin' does not appear to be a git repository"):
            self._comparing(process)

        assert not process.invoked("rev-list")

    def test_a_base_that_exists_locally_but_was_never_pushed_raises_naming_the_base_instead_of_a_git_command_failure(
        self,
    ) -> None:
        base = "slice/05-never-pushed"
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(
                *self.commits_behind_remote(base),
                code=128,
                stderr=GitBranchesOutputMother.base_that_does_not_resolve(base),
            ),
        )

        with pytest.raises(UnresolvableBaseError, match="slice/05-never-pushed"):
            self._comparing(process, base=base)

    def test_a_base_that_does_not_exist_anywhere_raises_naming_the_base_instead_of_a_git_command_failure(
        self,
    ) -> None:
        base = "never-existed"
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(
                *self.commits_behind_remote(base),
                code=128,
                stderr=GitBranchesOutputMother.base_that_does_not_resolve(base),
            ),
        )

        with pytest.raises(UnresolvableBaseError, match="never-existed"):
            self._comparing(process, base=base)


class TestGitBranchesCatchingUpTheBranch(BranchesCommands):
    def test_a_branch_left_behind_by_a_push_from_elsewhere_is_merged_with_its_remote_tip(self) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            Answer.to_exactly(*self.merge(remote), stdout=GitBranchesOutputMother.fast_forward()),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=0),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.caught_up()
        assert process.ran(*self.merge(remote))

    def test_a_base_that_gained_commits_since_the_branch_was_born_is_merged_into_the_branch(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.present(self.remote_slice_branch()),
            self.behind(self.remote_slice_branch(), by=0),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=1),
            self.merged(self.remote_base()),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.caught_up()
        assert self.merge_calls_of(process) == [list(self.merge(self.remote_base()))]

    def test_a_branch_with_commits_of_its_own_is_brought_up_to_date_by_merging_instead_of_rewriting_them(
        self,
    ) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            self.merged(remote),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=0),
        )

        outcome = self.catching_up(process)

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        assert process.ran(*self.merge(remote))
        assert not any(process.invoked(token) for token in ("rebase", "reset", "cherry-pick", "push"))

    def test_files_left_conflicting_close_the_merge_instead_of_leaving_the_worktree_half_merged(self) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            self.stopped_by_a_conflict(remote),
            self.merge_in_progress(),
            Answer.to_exactly(
                *self.unmerged_paths(),
                stdout=GitBranchesOutputMother.unmerged(*BranchCatchUpMother.CONFLICTING_PATHS),
            ),
            self.aborted(),
        )

        outcome = self.catching_up(process)

        assert outcome.outcome is BranchCatchUpOutcome.CONFLICTING
        assert process.calls[-1].argv == list(self.abort_merge())

    def test_files_left_conflicting_report_the_paths_git_marked_as_unmerged(self) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            self.stopped_by_a_conflict(remote),
            self.merge_in_progress(),
            Answer.to_exactly(
                *self.unmerged_paths(),
                stdout=GitBranchesOutputMother.unmerged(*BranchCatchUpMother.CONFLICTING_PATHS),
            ),
            self.aborted(),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.conflicting_on_a_shared_file()

    def test_a_failure_reading_the_conflicting_paths_still_aborts_the_merge_instead_of_leaving_it_half_merged(
        self,
    ) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgvRaisingOn(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            self.stopped_by_a_conflict(remote),
            self.merge_in_progress(),
            self.aborted(),
            when=("diff", "--name-only"),
            raises=ProcessTimedOutError("git diff: killed after 1s"),
        )

        with pytest.raises(ProcessTimedOutError):
            self.catching_up(process)

        assert process.calls[-1].argv == list(self.abort_merge())

    def test_a_conflicting_path_with_non_ascii_bytes_is_asked_for_literally_and_reported_as_given(self) -> None:
        remote = self.remote_slice_branch()
        non_ascii_path = "conclusión.md"
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            self.stopped_by_a_conflict(remote),
            self.merge_in_progress(),
            Answer.to_exactly(*self.unmerged_paths(), stdout=GitBranchesOutputMother.unmerged(non_ascii_path)),
            self.aborted(),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUp.conflicting(paths=(non_ascii_path,))

    def test_a_branch_that_is_already_up_to_date_with_both_remotes_makes_no_merge_call(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.present(self.remote_slice_branch()),
            self.behind(self.remote_slice_branch(), by=0),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=0),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.caught_up()
        assert not process.invoked("merge")

    def test_a_branch_never_pushed_to_its_own_remote_still_catches_up_from_the_base(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.absent(self.remote_slice_branch()),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=1),
            self.merged(self.remote_base()),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.caught_up()
        assert self.merge_calls_of(process) == [list(self.merge(self.remote_base()))]
        assert not process.ran(*self.commits_behind(self.remote_slice_branch()))

    def test_a_branch_never_pushed_to_its_own_remote_and_already_at_the_base_makes_no_merge_call(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.absent(self.remote_slice_branch()),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=0),
        )

        outcome = self.catching_up(process)

        assert outcome == BranchCatchUpMother.caught_up()
        assert not process.invoked("merge")

    def test_uncommitted_changes_left_by_a_crashed_invocation_raise_instead_of_reporting_a_conflict(self) -> None:
        remote = self.remote_slice_branch()
        process = AnsweringByArgv(
            self.fetched(),
            self.present(remote),
            self.behind(remote, by=1),
            Answer.to_exactly(
                *self.merge(remote),
                code=1,
                stderr=GitBranchesOutputMother.local_changes_overwritten_by_merge(),
            ),
            Answer.to_exactly(*self.merge_head(), code=1),
        )

        with pytest.raises(GitCommandFailedError, match="overwritten by merge"):
            self.catching_up(process)

        assert not process.invoked("--abort")

    def test_the_merge_forces_merge_ff_true_so_a_machine_wide_ff_only_setting_cannot_stop_a_genuine_merge(
        self,
    ) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.present(self.remote_slice_branch()),
            self.behind(self.remote_slice_branch(), by=0),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=1),
            self.merged(self.remote_base()),
        )

        self.catching_up(process)

        [merge] = self.merge_calls_of(process)
        assert ["-c", "merge.ff=true"] == merge[3:5]

    def test_the_merge_turns_commit_signing_off_so_a_machine_wide_gpgsign_setting_cannot_report_a_conflict(
        self,
    ) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            self.present(self.remote_slice_branch()),
            self.behind(self.remote_slice_branch(), by=0),
            self.present(self.remote_base()),
            self.behind(self.remote_base(), by=1),
            self.merged(self.remote_base()),
        )

        self.catching_up(process)

        [merge] = self.merge_calls_of(process)
        assert ["-c", "commit.gpgsign=false"] == merge[5:7]
