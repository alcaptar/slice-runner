from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.git_worktrees import GitWorktrees
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.git_worktrees_output_mother import GitWorktreesOutputMother
from slice_runner.tests.mothers.listed_worktree_mother import ListedWorktreeMother

if TYPE_CHECKING:
    from pathlib import Path


class WorktreesScenario:
    ROOT: ClassVar[str] = ListedWorktreeMother.ROOT
    BASE: ClassVar[str] = ListedWorktreeMother.BASE
    BRANCH: ClassVar[str] = "slice/01-the-slice"
    OTHER_BRANCH: ClassVar[str] = "slice/00-other"
    MISSING_BRANCH: ClassVar[str] = "slice/99-not-there"
    RULE: ClassVar[str] = SliceIdentity.worktrees_exclusion()
    MOUNTED_AT: ClassVar[str] = f"{ROOT}/{SliceIdentity.WORKTREES_DIRECTORY}/01-the-slice"
    GIT_DIRECTORY: ClassVar[str] = f"{ROOT}/.git"

    @staticmethod
    def worktrees(process: AnsweringByArgv) -> GitWorktrees:
        return GitWorktrees(process=process)

    @staticmethod
    def listing_command(root: str) -> tuple[str, ...]:
        return ("git", "-C", root, "worktree", "list", "--porcelain")

    @staticmethod
    def branch_command(root: str, name: str) -> tuple[str, ...]:
        return ("git", "-C", root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")

    @staticmethod
    def common_dir_command(path: str) -> tuple[str, ...]:
        return ("git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir")

    @staticmethod
    def fetch_command(root: str) -> tuple[str, ...]:
        return ("git", "-C", root, "fetch", "origin", "--quiet")

    @staticmethod
    def add_new_branch_command(root: str, path: str, branch: str, base: str) -> tuple[str, ...]:
        return ("git", "-C", root, "worktree", "add", "-b", branch, path, f"origin/{base}")

    @staticmethod
    def add_on_branch_command(root: str, path: str, branch: str) -> tuple[str, ...]:
        return ("git", "-C", root, "worktree", "add", path, branch)

    @staticmethod
    def prune_command(root: str) -> tuple[str, ...]:
        return ("git", "-C", root, "worktree", "prune")

    @staticmethod
    def status_command(path: str) -> tuple[str, ...]:
        return ("git", "-C", path, "status", "--porcelain")

    @staticmethod
    def local_only_command(root: str, branch: str) -> tuple[str, ...]:
        return ("git", "-C", root, "rev-list", "--count", f"refs/heads/{branch}", "--not", "--remotes")

    @staticmethod
    def remove_command(root: str, path: str) -> tuple[str, ...]:
        return ("git", "-C", root, "worktree", "remove", path)

    @staticmethod
    def delete_branch_command(root: str, branch: str) -> tuple[str, ...]:
        return ("git", "-C", root, "branch", "-D", branch)

    @classmethod
    def fetched(cls) -> Answer:
        return Answer.to_exactly(*cls.fetch_command(cls.ROOT))

    @classmethod
    def listing_of_the_clone_with_the_slice_mounted(cls) -> Answer:
        return Answer.to_exactly(
            *cls.listing_command(cls.ROOT),
            stdout=GitWorktreesOutputMother.listing(
                GitWorktreesOutputMother.main_clone(path=cls.ROOT, branch=cls.BASE),
                GitWorktreesOutputMother.mounted(path=cls.MOUNTED_AT, branch=cls.BRANCH),
            ),
        )

    @classmethod
    def outside_any_repository(cls, *command: str) -> Answer:
        return Answer.to_exactly(*command, code=128, stderr=GitWorktreesOutputMother.not_a_repository())


class TestGitWorktreesMountingTrees(WorktreesScenario):
    def test_a_new_branch_is_created_from_the_remote_base_together_with_its_worktree(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE)),
        )

        self.worktrees(process).add_new_branch(root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH, base=self.BASE)

        assert process.ran(*self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE))

    def test_the_remote_base_is_fetched_before_the_branch_is_cut_so_it_starts_at_the_remote_tip(self) -> None:
        add = self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE)
        process = AnsweringByArgv(self.fetched(), Answer.to_exactly(*add))

        self.worktrees(process).add_new_branch(root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH, base=self.BASE)

        assert [call.argv for call in process.calls] == [list(self.fetch_command(self.ROOT)), list(add)]

    def test_creating_the_branch_never_moves_the_local_base_branch(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(*self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE)),
        )

        self.worktrees(process).add_new_branch(root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH, base=self.BASE)

        assert not any(process.invoked(token) for token in ("pull", "merge", "reset", "checkout", "update-ref"))

    def test_a_new_branch_whose_name_is_already_taken_raises_instead_of_standing_on_the_old_one(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(
                *self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE),
                code=128,
                stderr=GitWorktreesOutputMother.branch_already_exists(self.BRANCH),
            ),
        )

        with pytest.raises(GitCommandFailedError, match=self.BRANCH):
            self.worktrees(process).add_new_branch(
                root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH, base=self.BASE
            )

    def test_a_branch_that_already_exists_is_mounted_without_being_created_again(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(*self.add_on_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH))
        )

        self.worktrees(process).add_on_branch(root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH)

        assert process.ran(*self.add_on_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH))
        assert not process.invoked("-b")

    def test_asking_to_mount_over_a_path_that_git_refuses_raises_instead_of_pretending(self) -> None:
        process = AnsweringByArgv(
            self.fetched(),
            Answer.to_exactly(
                *self.add_new_branch_command(self.ROOT, self.MOUNTED_AT, self.BRANCH, self.BASE),
                code=128,
                stderr=GitWorktreesOutputMother.path_already_exists(self.MOUNTED_AT),
            ),
        )

        with pytest.raises(GitCommandFailedError, match="already exists"):
            self.worktrees(process).add_new_branch(
                root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH, base=self.BASE
            )


class TestGitWorktreesListingTrees(WorktreesScenario):
    def test_the_listing_marks_the_main_clone_apart_from_the_worktrees_and_gives_branches_without_their_prefix(
        self,
    ) -> None:
        process = AnsweringByArgv(self.listing_of_the_clone_with_the_slice_mounted())

        listed = self.worktrees(process).listed(root=self.ROOT)

        assert listed == (
            ListedWorktreeMother.main_clone(on=self.BASE),
            ListedWorktreeMother.mounted(path=self.MOUNTED_AT, branch=self.BRANCH),
        )

    def test_the_listing_gives_no_branch_for_a_detached_worktree(self) -> None:
        detached = f"{self.ROOT}/.worktrees/detached"
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.listing_command(self.ROOT),
                stdout=GitWorktreesOutputMother.listing(
                    GitWorktreesOutputMother.main_clone(path=self.ROOT, branch=self.BASE),
                    GitWorktreesOutputMother.detached(path=detached),
                ),
            )
        )

        listed = self.worktrees(process).listed(root=self.ROOT)

        assert listed == (
            ListedWorktreeMother.main_clone(on=self.BASE),
            ListedWorktreeMother.detached(path=detached),
        )

    def test_a_worktree_whose_directory_was_deleted_by_hand_is_listed_as_prunable_until_it_is_pruned(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.listing_command(self.ROOT),
                stdout=GitWorktreesOutputMother.listing(
                    GitWorktreesOutputMother.main_clone(path=self.ROOT, branch=self.BASE),
                    GitWorktreesOutputMother.whose_directory_was_deleted(path=self.MOUNTED_AT, branch=self.BRANCH),
                ),
            ),
            Answer.to_exactly(*self.prune_command(self.ROOT)),
            Answer.to_exactly(
                *self.listing_command(self.ROOT),
                stdout=GitWorktreesOutputMother.listing(
                    GitWorktreesOutputMother.main_clone(path=self.ROOT, branch=self.BASE)
                ),
            ),
        )
        worktrees = self.worktrees(process)

        before = worktrees.listed(root=self.ROOT)
        worktrees.prune(root=self.ROOT)
        after = worktrees.listed(root=self.ROOT)

        assert before == (
            ListedWorktreeMother.main_clone(on=self.BASE),
            ListedWorktreeMother.whose_directory_was_deleted(path=self.MOUNTED_AT, branch=self.BRANCH),
        )
        assert after == (ListedWorktreeMother.main_clone(on=self.BASE),)

    def test_a_branch_that_exists_is_told_apart_from_one_that_does_not(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.branch_command(self.ROOT, self.BRANCH), stdout=GitWorktreesOutputMother.verified_ref()
            ),
            Answer.to_exactly(*self.branch_command(self.ROOT, self.MISSING_BRANCH), code=1),
        )
        worktrees = self.worktrees(process)

        assert (
            worktrees.branch_exists(root=self.ROOT, name=self.BRANCH),
            worktrees.branch_exists(root=self.ROOT, name=self.MISSING_BRANCH),
        ) == (True, False)

    def test_asking_about_a_branch_outside_any_repo_raises_instead_of_answering_false(self) -> None:
        process = AnsweringByArgv(self.outside_any_repository(*self.branch_command("/not-a-repo", self.BASE)))

        with pytest.raises(GitCommandFailedError, match="not a git repository"):
            self.worktrees(process).branch_exists(root="/not-a-repo", name=self.BASE)

    def test_a_tree_of_the_slice_on_its_path_is_mounted(self) -> None:
        process = AnsweringByArgv(self.listing_of_the_clone_with_the_slice_mounted())

        mounted = self.worktrees(process).is_mounted(root=self.ROOT, path=self.MOUNTED_AT, branch=self.BRANCH)

        assert mounted is True

    def test_a_path_with_no_tree_on_it_is_not_mounted(self) -> None:
        process = AnsweringByArgv(self.listing_of_the_clone_with_the_slice_mounted())

        mounted = self.worktrees(process).is_mounted(root=self.ROOT, path=f"{self.ROOT}/nothing", branch=self.BRANCH)

        assert mounted is False

    def test_a_tree_on_that_path_holding_another_branch_is_not_mounted_for_this_one(self) -> None:
        process = AnsweringByArgv(self.listing_of_the_clone_with_the_slice_mounted())

        mounted = self.worktrees(process).is_mounted(root=self.ROOT, path=self.MOUNTED_AT, branch=self.OTHER_BRANCH)

        assert mounted is False

    def test_asking_whether_a_tree_is_mounted_outside_any_repo_raises_instead_of_answering_false(self) -> None:
        process = AnsweringByArgv(self.outside_any_repository(*self.listing_command("/not-a-repo")))

        with pytest.raises(WorktreeRetirementError, match="not a git repository"):
            self.worktrees(process).is_mounted(root="/not-a-repo", path="/not-a-repo/x", branch=self.BRANCH)


class TestGitWorktreesWritingTheExclusion(WorktreesScenario):
    @staticmethod
    def _exclusion_of(git_directory: Path) -> Path:
        return git_directory / "info" / "exclude"

    def _asking_the_common_directory(self, git_directory: Path, *, from_path: str | None = None) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer.to_exactly(
                *self.common_dir_command(from_path or self.ROOT),
                stdout=GitWorktreesOutputMother.absolute_git_directory(str(git_directory)),
            )
        )

    def test_the_rule_is_written_once_into_the_exclusion_of_the_common_directory(self, tmp_path: Path) -> None:
        git_directory = tmp_path / "common"
        process = self._asking_the_common_directory(git_directory)

        self.worktrees(process).exclude(root=self.ROOT, rule=self.RULE)

        assert self._exclusion_of(git_directory).read_text().splitlines() == [self.RULE]

    def test_writing_the_rule_again_does_not_duplicate_it(self, tmp_path: Path) -> None:
        git_directory = tmp_path / "common"
        answer = Answer.to_exactly(
            *self.common_dir_command(self.ROOT),
            stdout=GitWorktreesOutputMother.absolute_git_directory(str(git_directory)),
        )
        worktrees = self.worktrees(AnsweringByArgv(answer, answer))

        worktrees.exclude(root=self.ROOT, rule=self.RULE)
        worktrees.exclude(root=self.ROOT, rule=self.RULE)

        assert self._exclusion_of(git_directory).read_text().splitlines().count(self.RULE) == 1

    def test_the_rule_goes_to_the_common_directory_even_when_asked_from_inside_a_worktree(self, tmp_path: Path) -> None:
        git_directory = tmp_path / "common"
        process = self._asking_the_common_directory(git_directory, from_path=self.MOUNTED_AT)

        self.worktrees(process).exclude(root=self.MOUNTED_AT, rule=self.RULE)

        assert process.ran(*self.common_dir_command(self.MOUNTED_AT))
        assert self._exclusion_of(git_directory).read_text().splitlines() == [self.RULE]

    def test_the_common_directory_of_a_worktree_is_the_git_directory_of_its_clone(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.common_dir_command(self.MOUNTED_AT),
                stdout=GitWorktreesOutputMother.absolute_git_directory(self.GIT_DIRECTORY),
            ),
            Answer.to_exactly(
                *self.common_dir_command(self.ROOT),
                stdout=GitWorktreesOutputMother.absolute_git_directory(self.GIT_DIRECTORY),
            ),
        )
        worktrees = self.worktrees(process)

        assert worktrees.common_dir(path=self.MOUNTED_AT) == self.GIT_DIRECTORY
        assert worktrees.common_dir(path=self.ROOT) == self.GIT_DIRECTORY

    def test_a_path_that_is_inside_no_repo_has_no_common_directory(self) -> None:
        process = AnsweringByArgv(
            self.outside_any_repository(*self.common_dir_command("/not-a-repo")),
            self.outside_any_repository(*self.common_dir_command("/does-not-exist")),
        )
        worktrees = self.worktrees(process)

        assert worktrees.common_dir(path="/not-a-repo") == ""
        assert worktrees.common_dir(path="/does-not-exist") == ""


class TestGitWorktreesAskingAboutAMountedTree(WorktreesScenario):
    def test_a_clean_tree_has_no_uncommitted_work(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(*self.status_command(self.MOUNTED_AT), stdout=GitWorktreesOutputMother.clean_status())
        )

        assert self.worktrees(process).has_uncommitted_work(path=self.MOUNTED_AT) is False

    def test_a_modified_tracked_file_is_uncommitted_work(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.status_command(self.MOUNTED_AT),
                stdout=GitWorktreesOutputMother.status_with_a_modified_tracked_file("tracked.txt"),
            )
        )

        assert self.worktrees(process).has_uncommitted_work(path=self.MOUNTED_AT) is True

    def test_a_file_git_does_not_track_yet_is_uncommitted_work_too(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.status_command(self.MOUNTED_AT),
                stdout=GitWorktreesOutputMother.status_with_an_untracked_file("new.txt"),
            )
        )

        assert self.worktrees(process).has_uncommitted_work(path=self.MOUNTED_AT) is True

    def test_a_staged_file_is_uncommitted_work(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.status_command(self.MOUNTED_AT),
                stdout=GitWorktreesOutputMother.status_with_a_staged_file("staged.txt"),
            )
        )

        assert self.worktrees(process).has_uncommitted_work(path=self.MOUNTED_AT) is True

    def test_asking_about_a_path_that_is_no_worktree_raises_instead_of_answering_that_nothing_is_there(self) -> None:
        missing = f"{self.ROOT}/does-not-exist"
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.status_command(missing),
                code=128,
                stderr=GitWorktreesOutputMother.cannot_change_to_a_missing_directory(missing),
            )
        )

        with pytest.raises(WorktreeRetirementError, match="No such file or directory"):
            self.worktrees(process).has_uncommitted_work(path=missing)

    def test_a_branch_cut_from_the_base_with_no_commit_of_its_own_has_nothing_only_local(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.local_only_command(self.ROOT, self.BRANCH), stdout=GitWorktreesOutputMother.commit_count(0)
            )
        )

        assert self.worktrees(process).local_only_commits(root=self.ROOT, branch=self.BRANCH) == 0

    def test_every_commit_that_no_remote_has_counts_as_only_local(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.local_only_command(self.ROOT, self.BRANCH), stdout=GitWorktreesOutputMother.commit_count(2)
            )
        )

        assert self.worktrees(process).local_only_commits(root=self.ROOT, branch=self.BRANCH) == 2

    def test_a_commit_that_was_pushed_is_left_out_of_the_count_by_asking_git_for_what_no_remote_has(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.local_only_command(self.ROOT, self.BRANCH), stdout=GitWorktreesOutputMother.commit_count(1)
            )
        )

        only_local = self.worktrees(process).local_only_commits(root=self.ROOT, branch=self.BRANCH)

        assert only_local == 1
        assert process.invoked("--not", "--remotes")

    def test_asking_about_a_branch_that_does_not_exist_raises_instead_of_answering_zero(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.local_only_command(self.ROOT, self.MISSING_BRANCH),
                code=128,
                stderr=GitWorktreesOutputMother.unknown_branch(self.MISSING_BRANCH),
            )
        )

        with pytest.raises(WorktreeRetirementError, match=self.MISSING_BRANCH):
            self.worktrees(process).local_only_commits(root=self.ROOT, branch=self.MISSING_BRANCH)


class TestGitWorktreesRetiringATree(WorktreesScenario):
    def test_removing_a_clean_tree_asks_git_to_remove_it_without_forcing(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.remove_command(self.ROOT, self.MOUNTED_AT)))

        self.worktrees(process).remove(root=self.ROOT, path=self.MOUNTED_AT)

        assert process.ran(*self.remove_command(self.ROOT, self.MOUNTED_AT))
        assert not process.invoked("--force")

    def test_removing_a_tree_with_uncommitted_work_is_refused_by_git_and_never_forced(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.remove_command(self.ROOT, self.MOUNTED_AT),
                code=128,
                stderr=GitWorktreesOutputMother.removal_refused_for_uncommitted_work(self.MOUNTED_AT),
            )
        )

        with pytest.raises(WorktreeRetirementError, match="contains modified or untracked files"):
            self.worktrees(process).remove(root=self.ROOT, path=self.MOUNTED_AT)

        assert not process.invoked("--force")

    def test_deleting_the_branch_of_a_tree_that_is_gone_asks_git_to_delete_it(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.delete_branch_command(self.ROOT, self.BRANCH)))

        self.worktrees(process).delete_branch(root=self.ROOT, branch=self.BRANCH)

        assert process.ran(*self.delete_branch_command(self.ROOT, self.BRANCH))

    def test_deleting_a_branch_that_does_not_exist_raises(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly(
                *self.delete_branch_command(self.ROOT, self.MISSING_BRANCH),
                code=1,
                stderr=GitWorktreesOutputMother.branch_not_found(self.MISSING_BRANCH),
            )
        )

        with pytest.raises(WorktreeRetirementError, match="not found"):
            self.worktrees(process).delete_branch(root=self.ROOT, branch=self.MISSING_BRANCH)
