from __future__ import annotations

import re
from typing import ClassVar

import pytest
from conftest import _ROOT, _read

from slice_runner.domain.order import Order
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.subcommand import Subcommand


class TestEveryOrderIsASubcommandOfTheProgram:
    @pytest.mark.parametrize("order", list(Order))
    def test_the_order_is_a_subcommand_of_the_program(self, order: Order) -> None:
        assert str(order) in {str(subcommand) for subcommand in Subcommand}

    @pytest.mark.parametrize("order", list(Order))
    def test_the_parser_knows_it(self, order: Order) -> None:
        assert str(order) in Cli.parser().format_help()


class TestNoDocumentOrTemplateOffersACommentAsAnOrder:
    TOKEN: ClassVar[re.Pattern[str]] = re.compile(r"(?<![A-Za-z-])-(?:GO|REVIEW|RETRY)(?![A-Za-z])")
    PATHS: ClassVar[tuple[str, ...]] = ("skills/slice-spec/SKILL.md",)

    @pytest.mark.parametrize("path", PATHS)
    def test_the_file_mentions_none_of_the_comment_tokens_as_a_whole_word(self, path: str) -> None:
        assert self.TOKEN.findall(_read(_ROOT / path)) == []

    @pytest.mark.parametrize("text", ["-GO", "responde `-REVIEW <x>`", "(-RETRY)", "a -GO."])
    def test_the_pattern_catches_a_token_standing_alone(self, text: str) -> None:
        assert self.TOKEN.search(text) is not None

    @pytest.mark.parametrize("text", ["NO-GO", "--GO", "-GOAL", "-REVIEWER", "-RETRYING"])
    def test_the_pattern_ignores_a_token_glued_to_a_dash_or_a_letter(self, text: str) -> None:
        assert self.TOKEN.search(text) is None
