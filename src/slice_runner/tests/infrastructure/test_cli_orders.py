from __future__ import annotations

import json

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.retired_issue_label import RetiredIssueLabel
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.tests.argv import Argv
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.gh_conversation_mother import GhConversationMother
from slice_runner.tests.mothers.run_mother import RunMother

_REPO = GhConversationMother.REPO
_ISSUE = GhConversationMother.SUBISSUE
_TOKENS = ("-GO", "-REVIEW", "-RETRY")
RETIREMENTS = [
    ("bloqueada:higiene", "bloqueada:controles"),
    ("bloqueada:verify", "bloqueada:juez"),
    ("bloqueada:sin-cambios", "bloqueada:juez"),
    ("bloqueada:worktree-sin-retirar", "bloqueada:worktree"),
]


class _Orders:
    @staticmethod
    def process(view: dict[str, object]) -> AnsweringByArgv:
        body = view["body"]
        assert isinstance(body, str)

        return AnsweringByArgv(
            Answer(to=("view", "--json", "number,title,body,labels,state"), stdout=json.dumps(view)),
            Answer(to=("view", "--json", "body"), stdout=json.dumps({"body": body})),
            Answer(to=("edit", "--body-file")),
            Answer(to=("edit", "--add-label")),
            Answer(to=("comment",)),
        )

    @staticmethod
    def blocked_on_red_ci() -> dict[str, object]:
        return GhConversationMother.the_subissue_viewed(
            label=IssueLabel.BLOCKED_CI_RED, run=RunMother.blocked_on_red_ci()
        )

    @staticmethod
    def written_block(process: AnsweringByArgv) -> dict[str, object]:
        rewritten = next(call for call in process.calls if "--body-file" in call.argv)
        raw = rewritten.stdin.split("<!-- slice-runner:estado\n", maxsplit=1)[1].split("\n-->", maxsplit=1)[0]
        block = json.loads(raw)
        assert isinstance(block, dict)

        return block

    @staticmethod
    def left_comment(process: AnsweringByArgv) -> str:
        return next(call.stdin for call in process.calls if "comment" in call.argv)

    @staticmethod
    def wrote_nothing(process: AnsweringByArgv) -> bool:
        return not any("edit" in call.argv or "comment" in call.argv for call in process.calls)

    @staticmethod
    def only_talked_to_github(process: AnsweringByArgv) -> bool:
        return all(call.argv[0] == "gh" for call in process.calls)


class TestRetry(_Orders):
    def test_it_reopens_the_slice_by_its_label_and_resets_the_counter_that_blocked_it(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        code = Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        edit = next(call for call in process.calls if "--add-label" in call.argv)
        block = self.written_block(process)
        assert code == ExitCode.OK
        assert Argv(edit.argv).value_of("--remove-label") == IssueLabel.BLOCKED_CI_RED.value
        assert Argv(edit.argv).value_of("--add-label") == IssueLabel.IN_PROGRESS.value
        assert block["ci_retries"] == 0

    def test_it_saves_the_instruction_in_the_run_so_a_process_that_dies_cannot_lose_it(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        assert self.written_block(process)["retry_instruction"] == "ya esta a mano"

    def test_it_leaves_a_comment_with_the_text_and_without_any_token(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="ya esta a mano")

        comment = self.left_comment(process)
        assert "`retry`" in comment
        assert "ya esta a mano" in comment
        assert not any(token in comment for token in _TOKENS)

    def test_it_never_launches_the_run_or_the_model(self) -> None:
        process = self.process(self.blocked_on_red_ci())

        Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="x")

        assert self.only_talked_to_github(process)

    @pytest.mark.parametrize(
        "view",
        [
            GhConversationMother.the_subissue_viewed(label=IssueLabel.PENDING),
            GhConversationMother.the_subissue_viewed(label=IssueLabel.IN_PROGRESS, run=RunMother.implementing()),
        ],
    )
    def test_a_slice_that_is_neither_blocked_nor_aborted_is_refused_with_its_own_code_and_writes_nothing(
        self, view: dict[str, object], capsys: pytest.CaptureFixture[str]
    ) -> None:
        process = self.process(view)

        code = Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="x")

        captured = capsys.readouterr()
        assert code == ExitCode.ORDER_REFUSED
        assert "neither blocked nor aborted" in captured.err
        assert self.wrote_nothing(process)


class TestRetryOnASliceCarryingARetiredLabel(_Orders):
    @pytest.mark.parametrize(("retired", "replacement"), RETIREMENTS)
    def test_it_fails_naming_the_retired_label_and_the_one_that_replaced_it_and_writes_nothing(
        self, retired: str, replacement: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        view = GhConversationMother.the_subissue_viewed(
            label=RetiredIssueLabel(retired), run=RunMother.blocked_on_controls()
        )
        process = self.process(view)

        code = Cli(process=process, budgets=Budgets()).retry(repo=_REPO, issue=_ISSUE, instruction="x")

        reported = capsys.readouterr().err
        assert code == ExitCode.USAGE_ERROR
        assert retired in reported
        assert replacement in reported
        assert self.wrote_nothing(process)


class TestTheParserOfTheOrders:
    def test_retry_takes_the_text_after_the_options_as_several_words(self) -> None:
        arguments = Cli.parser().parse_args(["retry", "45", "--repo", _REPO, "ya", "esta"])

        assert arguments.text == ["ya", "esta"]

    def test_the_text_is_required(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["retry", "45", "--repo", _REPO])

        assert "text" in capsys.readouterr().err

    def test_the_repo_is_required(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args(["retry", "45", "texto"])

        assert "--repo" in capsys.readouterr().err

    @pytest.mark.parametrize("retired", ["go", "review", "understanding"])
    def test_the_subcommands_of_the_retired_understanding_are_rejected(
        self, retired: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            Cli.parser().parse_args([retired, "45", "--repo", _REPO])

        assert "invalid choice" in capsys.readouterr().err
