from __future__ import annotations

import json
import os
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import ConversationNotFoundError, UnreadableConversationError
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_conversation_log import LocalConversationLog
from slice_runner.tests.mothers.conversation_transcript_mother import ConversationTranscriptMother

if TYPE_CHECKING:
    from pathlib import Path

_WORKTREE = ConversationTranscriptMother.WORKTREE
_WARNING_EXCERPT = (
    "\x1b[1m\x1b[33mwarning\x1b[39m\x1b[0m\x1b[1m:\x1b[0m \x1b[1m`VIRTUAL_ENV=/Users/someone/repos/demo-workspace/"
    ".venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target "
    "the active environment instead\x1b[0m Using CPython \x1b[36m3.14.3\x1b[39m\x1b[36m\x1b[39m Creating virtual "
    "environment at: \x1b[36m.venv\x1b[39m \x1b[36m\x1b[1mBuilding\x1b[0m\x1b[39m demo-workspace\x1b[2m @ "
    "file:///Users/someone/repos/worktree1\x1b[0m \x1b[32m\x1b[1mBuilt\x1b[0m\x1b[39m demo-workspace\x1b[2m @ "
    "file:///Users/someone/repos/worktree1\x1b[0m \x1b[2mI"
)


class WithARecordedConversation:
    @pytest.fixture(autouse=True)
    def transcript(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ConversationTranscriptMother.written_under(tmp_path)


class TestTheTurnsOfARecordedConversation(WithARecordedConversation):
    def test_every_assistant_line_is_counted_as_a_turn_even_a_thinking_only_one(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert [turn.number for turn in conversation.turns] == [1, 2, 3, 4]

    def test_the_text_a_turn_said_is_kept_as_what_it_decided(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert conversation.turns[0].text == "Now let's confirm RED before implementing:"

    def test_a_turn_with_no_text_because_it_only_carried_a_tool_call_or_thinking_has_none(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert conversation.turns[1].text == ""
        assert conversation.turns[2].text == ""

    def test_the_tool_a_turn_called_is_kept_with_its_input_as_the_summary(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        called = conversation.turns[1].tool_calls
        assert len(called) == 1
        assert called[0].name == "Bash"
        assert "uv run pytest src/slice_runner/tests/infrastructure/test_local_process.py" in called[0].summary

    def test_the_result_of_the_tool_call_is_kept_as_what_it_read(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert conversation.turns[1].tool_calls[0].result == _WARNING_EXCERPT
        assert conversation.turns[3].tool_calls[0].result == "18: process_timeout_seconds: int = 3600"

    def test_a_thinking_only_turn_has_no_tool_call(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert conversation.turns[2].tool_calls == ()


class TestWhetherACallWasRefused(WithARecordedConversation):
    def test_a_call_the_harness_answered_without_an_error_is_not_marked_as_failed(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert [call.failed for turn in conversation.turns for call in turn.tool_calls] == [False, False]

    def test_a_call_the_harness_refused_is_marked_so_the_durable_record_shows_the_fight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ConversationTranscriptMother.written_under(
            tmp_path, recorded=ConversationTranscriptMother.REJECTED_STRUCTURED_OUTPUT
        )

        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        refused = [call for turn in conversation.turns for call in turn.tool_calls if call.failed]
        assert [call.name for call in refused] == ["StructuredOutput"]


class TestTheSpendOfARecordedConversation(WithARecordedConversation):
    def test_the_usage_of_every_distinct_message_is_summed_only_once_even_if_it_is_split_across_lines(self) -> None:
        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        spend = conversation.spend
        assert (spend.input_tokens, spend.output_tokens) == (4, 450)
        assert (spend.cache_creation_tokens, spend.cache_read_tokens) == (3752, 418026)


class TestThePathATurnTouched:
    @staticmethod
    def _conversation_with(tool_name: str, tool_input: dict[str, object], *, tmp_path: Path) -> Path:
        destination = ConversationTranscriptMother.destination_of(tmp_path, session="path-session")
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "id": "msg_1",
                    "content": [{"type": "tool_use", "id": "toolu_1", "name": tool_name, "input": tool_input}],
                    "usage": {},
                },
            }
        )
        destination.write_text(f"{line}\n", encoding="utf-8")

        return destination

    def test_a_read_tool_use_carries_the_file_it_read(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._conversation_with("Read", {"file_path": "src/x.py"}, tmp_path=tmp_path)

        conversation = LocalConversationLog().read(session="path-session", worktree=_WORKTREE)

        assert conversation.turns[0].tool_calls[0].path == "src/x.py"

    def test_a_glob_tool_use_carries_the_path_it_searched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._conversation_with("Glob", {"path": "src", "pattern": "*.py"}, tmp_path=tmp_path)

        conversation = LocalConversationLog().read(session="path-session", worktree=_WORKTREE)

        assert conversation.turns[0].tool_calls[0].path == "src"

    def test_a_bash_tool_use_carries_no_path_because_a_command_is_not_a_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._conversation_with("Bash", {"command": "ls"}, tmp_path=tmp_path)

        conversation = LocalConversationLog().read(session="path-session", worktree=_WORKTREE)

        assert conversation.turns[0].tool_calls[0].path is None

    def test_a_bash_tool_use_carries_the_command_it_ran(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._conversation_with("Bash", {"command": "ls"}, tmp_path=tmp_path)

        conversation = LocalConversationLog().read(session="path-session", worktree=_WORKTREE)

        assert conversation.turns[0].tool_calls[0].command == "ls"

    def test_a_tool_use_that_is_not_bash_carries_its_path_and_no_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        self._conversation_with("Read", {"file_path": "src/x.py"}, tmp_path=tmp_path)

        call = LocalConversationLog().read(session="path-session", worktree=_WORKTREE).turns[0].tool_calls[0]

        assert (call.path, call.command) == ("src/x.py", None)


class TestWhereTheConversationLives:
    def test_a_worktree_whose_path_carries_dots_is_still_found_where_the_harness_keeps_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ConversationTranscriptMother.written_under(tmp_path)

        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert len(conversation.turns) == 4

    @pytest.mark.parametrize(
        ("relative", "invoked_from"),
        [
            (".", _WORKTREE),
            ("the-slice", str(PurePosixPath(_WORKTREE).parent)),
            (f"{PurePosixPath(_WORKTREE).name}/", str(PurePosixPath(_WORKTREE).parent)),
        ],
    )
    def test_a_relative_worktree_finds_the_same_conversation_as_its_absolute_equivalent(
        self, relative: str, invoked_from: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ConversationTranscriptMother.written_under(tmp_path)
        monkeypatch.setattr(os, "getcwd", lambda: invoked_from)

        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=relative)

        assert len(conversation.turns) == 4

    def test_an_absolute_worktree_is_found_wherever_the_program_was_invoked_from(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        ConversationTranscriptMother.written_under(tmp_path)
        monkeypatch.setattr(os, "getcwd", lambda: "/somewhere/else")

        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=_WORKTREE)

        assert len(conversation.turns) == 4

    def test_a_worktree_through_a_symbolic_link_is_looked_up_as_it_was_given_not_where_it_points(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        configuration = tmp_path / "configuration"
        real = tmp_path / "workspace" / "real"
        link = tmp_path / "workspace" / "link"
        real.mkdir(parents=True)
        link.symlink_to(real)
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(configuration))
        ConversationTranscriptMother.written_for_the_directory(configuration, directory=link)

        conversation = LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=str(link))

        assert len(conversation.turns) == 4
        with pytest.raises(ConversationNotFoundError):
            LocalConversationLog().read(session=ConversationTranscriptMother.SESSION, worktree=str(real))

    def test_a_session_never_recorded_under_that_repo_is_refused_instead_of_guessing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        with pytest.raises(ConversationNotFoundError):
            LocalConversationLog().read(session="never-recorded", worktree=_WORKTREE)


class TestAnUnreadableTranscript:
    def test_a_line_that_is_not_json_is_refused_instead_of_silently_dropped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        session = "broken-session"
        ConversationTranscriptMother.destination_of(tmp_path, session=session).write_text(
            "not json at all\n", encoding="utf-8"
        )

        with pytest.raises(UnreadableConversationError):
            LocalConversationLog().read(session=session, worktree=_WORKTREE)

    def test_a_tool_use_block_whose_input_is_not_an_object_is_refused_instead_of_stringified(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        session = "broken-session"
        destination = ConversationTranscriptMother.destination_of(tmp_path, session=session)
        line = (
            '{"type":"assistant","message":{"id":"msg_1","content":'
            '[{"type":"tool_use","id":"toolu_1","name":"Bash","input":"not an object"}],"usage":{}}}'
        )
        destination.write_text(f"{line}\n", encoding="utf-8")

        with pytest.raises(UnreadableConversationError):
            LocalConversationLog().read(session=session, worktree=_WORKTREE)
