from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from conftest import _ROOT

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class TuiScan:
    SOURCES: ClassVar[Path] = _ROOT / "tui" / "src"
    STRING_OR_CHAR: ClassVar[re.Pattern[str]] = re.compile(
        r"""r(#*)".*?"\1|b?"(?:\\.|[^"\\])*"|b?'(?:\\.|[^'\\])'""", re.DOTALL
    )
    COMMENT: ClassVar[re.Pattern[str]] = re.compile(r"//|/\*")
    RELATIVE_PATH: ClassVar[re.Pattern[str]] = re.compile(r"(?<![\w:])(?:super|self)::")
    OUTER_CRATE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:ratatui|crossterm|serde\w*|portable_pty|vt100|tui_term)::"
    )
    LAUNCH: ClassVar[re.Pattern[str]] = re.compile(r"\b(?:Command|CommandBuilder)::new\b")
    KILL: ClassVar[re.Pattern[str]] = re.compile(r"\.kill\(\)")

    @classmethod
    def files(cls) -> list[Path]:
        return sorted(cls.SOURCES.rglob("*.rs"))

    @classmethod
    def production_files(cls) -> list[Path]:
        return [path for path in cls.files() if "tests" not in path.relative_to(cls.SOURCES).parts]

    @classmethod
    def domain_files(cls) -> list[Path]:
        return [path for path in cls.files() if path.relative_to(cls.SOURCES).parts[0] == "domain"]

    @classmethod
    def code_of(cls, source: str) -> str:
        return cls.STRING_OR_CHAR.sub('""', source)

    @classmethod
    def has_prose(cls, source: str) -> bool:
        return cls.COMMENT.search(cls.code_of(source)) is not None

    @classmethod
    def uses_a_relative_path(cls, source: str) -> bool:
        return cls.RELATIVE_PATH.search(cls.code_of(source)) is not None

    @classmethod
    def reaches_an_outer_crate(cls, source: str) -> bool:
        return cls.OUTER_CRATE.search(cls.code_of(source)) is not None

    @classmethod
    def launches_without_killing(cls, source: str) -> bool:
        code = cls.code_of(source)

        return cls.LAUNCH.search(code) is not None and cls.KILL.search(code) is None

    @staticmethod
    def offenders(paths: list[Path], check: Callable[[str], bool]) -> list[str]:
        return [str(path.relative_to(_ROOT)) for path in paths if check(path.read_text(encoding="utf-8"))]


class TestTheScanReachesTheTreeAndStripsLiterals:
    def test_the_scan_finds_the_entrypoint_of_the_interface(self) -> None:
        assert TuiScan.SOURCES / "main.rs" in TuiScan.production_files()

    def test_a_double_slash_inside_a_string_is_not_prose(self) -> None:
        assert not TuiScan.has_prose('struct Link;\nimpl Link { const URL: &str = "https://x.y/z"; }')
        assert not TuiScan.has_prose('const RAW: &str = r#"a // b"#;')

    def test_a_quote_inside_a_char_literal_does_not_hide_the_rest_of_the_line(self) -> None:
        assert TuiScan.has_prose("const QUOTE: char = '\"'; // note")


class TestTheCodeOfTheInterfaceCarriesNoProse:
    def test_a_line_comment_a_doc_comment_and_a_block_comment_trip_the_scan(self) -> None:
        assert TuiScan.has_prose("fn main() {} // why")
        assert TuiScan.has_prose("/// what\nstruct A;")
        assert TuiScan.has_prose("//! module\n")
        assert TuiScan.has_prose("/* block */ struct A;")

    def test_no_file_of_the_interface_has_a_comment(self) -> None:
        assert TuiScan.offenders(TuiScan.files(), TuiScan.has_prose) == []


class TestTheInterfaceImportsByAbsolutePath:
    def test_a_path_through_super_or_self_trips_the_scan(self) -> None:
        assert TuiScan.uses_a_relative_path("use super::Thing;")
        assert TuiScan.uses_a_relative_path("use self::inner::Thing;")
        assert TuiScan.uses_a_relative_path("let value = super::make();")

    def test_self_inside_a_braced_import_and_the_self_type_do_not_trip_it(self) -> None:
        assert not TuiScan.uses_a_relative_path(
            "use std::io::{self, Write};\nimpl A { fn new() -> Self { Self::default() } }"
        )
        assert not TuiScan.uses_a_relative_path("use crate::domain::thing::Thing;")

    def test_no_file_of_the_interface_imports_by_a_relative_path(self) -> None:
        assert TuiScan.offenders(TuiScan.files(), TuiScan.uses_a_relative_path) == []


class TestTheDomainKnowsNoOuterCrate:
    def test_the_screen_the_terminal_and_the_serializer_trip_the_scan(self) -> None:
        assert TuiScan.reaches_an_outer_crate("use ratatui::widgets::List;")
        assert TuiScan.reaches_an_outer_crate("use crossterm::event::Event;")
        assert TuiScan.reaches_an_outer_crate("use serde::Deserialize;")
        assert TuiScan.reaches_an_outer_crate("let line = serde_json::from_str(raw);")

    def test_the_pseudoterminal_the_screen_emulator_and_its_widget_trip_the_scan(self) -> None:
        assert TuiScan.reaches_an_outer_crate("use portable_pty::native_pty_system;")
        assert TuiScan.reaches_an_outer_crate("use vt100::Parser;")
        assert TuiScan.reaches_an_outer_crate("use tui_term::widget::PseudoTerminal;")

    def test_the_standard_library_and_the_crate_itself_do_not_trip_it(self) -> None:
        assert not TuiScan.reaches_an_outer_crate("use std::collections::BTreeMap;\nuse crate::domain::slice::Slice;")

    def test_no_file_of_the_domain_reaches_an_outer_crate(self) -> None:
        assert TuiScan.offenders(TuiScan.domain_files(), TuiScan.reaches_an_outer_crate) == []


class TestEveryLaunchedProcessCanBeKilled:
    def test_a_launch_with_no_kill_in_the_same_file_trips_the_scan(self) -> None:
        assert TuiScan.launches_without_killing('let out = Command::new("slice-runner").output();')

    def test_a_pseudoterminal_launch_with_no_kill_in_the_same_file_trips_the_scan(self) -> None:
        assert TuiScan.launches_without_killing('let command = CommandBuilder::new("claude");')

    def test_a_pseudoterminal_launch_whose_file_kills_the_child_does_not_trip_it(self) -> None:
        assert not TuiScan.launches_without_killing('let command = CommandBuilder::new("claude");\nchild.kill();')

    def test_a_launch_whose_file_kills_the_child_does_not_trip_it(self) -> None:
        assert not TuiScan.launches_without_killing('let child = Command::new("slice-runner").spawn();\nchild.kill();')

    def test_no_production_file_launches_a_process_it_cannot_kill(self) -> None:
        assert TuiScan.offenders(TuiScan.production_files(), TuiScan.launches_without_killing) == []
