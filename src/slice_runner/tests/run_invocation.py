from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from slice_runner.application.actions.conduct_slice import ConductSliceParams
from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.cli import Cli
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother


class RunInvocation:
    common_dir: ClassVar[Path] = Path("/nowhere/.git")

    def __init__(
        self,
        *,
        children: str,
        answers: tuple[Answer, ...] = (),
        parent: str = GhConversationMother.parent_of_one_slice(),
        mounted: bool = True,
    ) -> None:
        self.process = AnsweringByArgv(
            Answer(to=("git", "rev-parse", "--git-common-dir"), stdout=f"{self.common_dir}\n"),
            Answer(to=("git", "worktree", "list", "--porcelain"), stdout=self._listing(mounted=mounted)),
            Answer(
                to=("git", "rev-parse", "--verify", "--quiet", f"refs/heads/{GhConversationMother.BRANCH}"),
                code=0 if mounted else 1,
            ),
            Answer(to=("gh", "issue", "view", "body,subIssuesSummary,state"), stdout=parent),
            Answer(to=("gh", "issue", "list"), stdout=children),
            *answers,
            Answer(to=("git", "symbolic-ref"), stdout=f"{GhConversationMother.BRANCH}\n"),
            Answer(to=("git", "diff", "--cached", "--name-only")),
            Answer(to=("git", "commit")),
            Answer(to=("gh", "issue", "view", "body"), stdout=GhConversationMother.body_of_the_subissue()),
            Answer(to=("gh", "issue", "edit")),
            Answer(to=("gh", "issue", "comment")),
            Answer(to=("cat", "CLAUDE.md"), stdout="reglas del repo"),
            Answer(to=("git", "fetch", "origin")),
            Answer(to=("git", "worktree", "add")),
        )

    def conduct(
        self,
        *,
        logs: Path,
        base: str = GhConversationMother.BASE,
        slice_id: str | None = None,
        budgets: Budgets | None = None,
        issue: int = GhConversationMother.ISSUE,
        worktree: str | None = GhConversationMother.WORKTREE,
    ) -> int:
        return Cli(process=self.process, budgets=budgets or Budgets()).run(
            self.params(logs=logs, base=base, slice_id=slice_id, issue=issue, worktree=worktree)
        )

    @staticmethod
    def params(
        *,
        logs: Path,
        base: str = GhConversationMother.BASE,
        slice_id: str | None = None,
        issue: int = GhConversationMother.ISSUE,
        worktree: str | None = GhConversationMother.WORKTREE,
    ) -> ConductSliceParams:
        return ConductSliceParams(
            repo=GhConversationMother.REPO,
            issue=issue,
            root=GhConversationMother.ROOT,
            worktree=worktree,
            base=base,
            logs=logs,
            slice_id=slice_id,
        )

    @staticmethod
    def _listing(*, mounted: bool) -> str:
        main = f"worktree {GhConversationMother.ROOT}\nHEAD 0000\nbranch refs/heads/{GhConversationMother.BASE}\n"
        if not mounted:
            return main

        return (
            f"{main}\nworktree {GhConversationMother.WORKTREE}\nHEAD 0000\n"
            f"branch refs/heads/{GhConversationMother.BRANCH}\n"
        )
