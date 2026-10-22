from __future__ import annotations

import json
from typing import ClassVar

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.process import ProcessNotRunnableError
from slice_runner.tests.doubles import Answer, AnsweringByArgv, AnsweringByArgvRaisingOn
from slice_runner.tests.mothers.git_diff_output_mother import GitDiffOutputMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother


class VerifyProcessMother:
    WORKTREE: ClassVar[str] = GitDiffOutputMother.WORKTREE
    BASE: ClassVar[str] = GitDiffOutputMother.BASE

    @classmethod
    def judging(
        cls, envelope: dict[str, object] | None = None, *, worktree: str = WORKTREE, base: str = BASE
    ) -> AnsweringByArgv:
        return AnsweringByArgv(
            *cls._staged(worktree=worktree, base=base),
            cls._judge(envelope or HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing())),
        )

    @classmethod
    def with_an_unrunnable_judge(cls, *, worktree: str = WORKTREE, base: str = BASE) -> AnsweringByArgvRaisingOn:
        return AnsweringByArgvRaisingOn(
            *cls._staged(worktree=worktree, base=base),
            when=(JudgeInvocation.EXECUTABLE,),
            raises=ProcessNotRunnableError(f"{JudgeInvocation.EXECUTABLE}: no such executable"),
        )

    @classmethod
    def with_nothing_staged(cls, *, worktree: str = WORKTREE, base: str = BASE) -> AnsweringByArgv:
        return AnsweringByArgv(Answer.to_exactly(*cls._diff(worktree, base, "--name-only"), stdout=""))

    @classmethod
    def with_a_base_that_does_not_resolve(cls, *, worktree: str = WORKTREE, base: str) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer.to_exactly(
                *cls._diff(worktree, base, "--name-only"),
                code=GitDiffOutputMother.UNKNOWN_BASE_CODE,
                stderr=GitDiffOutputMother.UNKNOWN_BASE_STDERR,
            )
        )

    @classmethod
    def with_a_worktree_that_is_not_a_repo(cls, *, worktree: str = WORKTREE, base: str = BASE) -> AnsweringByArgv:
        return AnsweringByArgv(
            Answer.to_exactly(
                *cls._diff(worktree, base, "--name-only"),
                code=GitDiffOutputMother.NOT_A_REPO_DIFF_CODE,
                stderr=GitDiffOutputMother.NOT_A_REPO_DIFF_STDERR,
            )
        )

    @classmethod
    def _staged(cls, *, worktree: str, base: str) -> tuple[Answer, ...]:
        return (
            Answer.to_exactly(
                *cls._diff(worktree, base, "--name-only"), stdout=GitDiffOutputMother.EDITED_MODULE_NAMES
            ),
            Answer.to_exactly(*cls._diff(worktree, base), stdout=GitDiffOutputMother.EDITED_MODULE_TEXT),
            Answer.to_exactly(
                *cls._diff(worktree, base, "--numstat"), stdout=GitDiffOutputMother.EDITED_MODULE_NUMSTAT
            ),
        )

    @staticmethod
    def _diff(worktree: str, base: str, *extra: str) -> list[str]:
        return ["git", "-C", worktree, "diff", "--cached", *extra, "--merge-base", base]

    @staticmethod
    def _judge(envelope: dict[str, object]) -> Answer:
        return Answer(to=(JudgeInvocation.EXECUTABLE,), stdout=json.dumps(envelope))
