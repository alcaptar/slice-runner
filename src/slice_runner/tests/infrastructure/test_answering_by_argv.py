from __future__ import annotations

import pytest

from slice_runner.tests.doubles import Answer, AnsweringByArgv


class TestAnsweringTheExactArgv:
    def test_an_answer_for_the_exact_argv_is_given_for_that_argv(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly("git", "status", stdout="clean"))

        assert process.run(["git", "status"], stdin="").stdout == "clean"

    def test_an_exact_answer_is_not_given_for_an_argv_that_only_contains_its_tokens(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly("git", "status", stdout="clean"))

        with pytest.raises(AssertionError, match="no answer was scripted for `git status --short`"):
            process.run(["git", "status", "--short"], stdin="")

    def test_an_argv_nobody_wrote_an_answer_for_fails_the_test_with_the_request_in_the_message(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly("git", "status"))

        with pytest.raises(AssertionError, match="no answer was scripted for `git log`"):
            process.run(["git", "log"], stdin="")


class TestSuccessiveAnswersForTheSameArgv:
    def test_each_call_gets_the_next_answer_in_the_order_they_were_written(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly("gh", "pr", "view", stdout="open"),
            Answer.to_exactly("gh", "pr", "view", stdout="merged"),
        )

        seen = [process.run(["gh", "pr", "view"], stdin="").stdout for _ in range(2)]

        assert seen == ["open", "merged"]

    def test_a_call_beyond_the_answers_written_fails_instead_of_repeating_the_last_one(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly("gh", "pr", "view", stdout="open"))
        process.run(["gh", "pr", "view"], stdin="")

        with pytest.raises(AssertionError, match="no answer was scripted for `gh pr view`"):
            process.run(["gh", "pr", "view"], stdin="")

    def test_the_answers_of_one_argv_do_not_consume_the_answers_of_another(self) -> None:
        process = AnsweringByArgv(
            Answer.to_exactly("gh", "pr", "view", stdout="open"),
            Answer.to_exactly("gh", "pr", "list", stdout="none"),
        )

        seen = [process.run(argv, stdin="").stdout for argv in (["gh", "pr", "list"], ["gh", "pr", "view"])]

        assert seen == ["none", "open"]


class TestAnswersByTokenKeepAnsweringEveryTime:
    def test_a_token_answer_is_given_again_on_every_call_that_contains_its_tokens(self) -> None:
        process = AnsweringByArgv(Answer(to=("status",), stdout="clean"))

        seen = [process.run(["git", "status"], stdin="").stdout for _ in range(2)]

        assert seen == ["clean", "clean"]
