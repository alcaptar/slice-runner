from __future__ import annotations

import re
from typing import ClassVar

from conftest import _ROOT, _read, _rel


class MakeInstallInSources:
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"\bmake\s+(?:-C\s+\S+\s+)?install")
    EXEMPT_TREE: ClassVar[str] = "src/slice_runner/tests/"

    @classmethod
    def naming(cls, sources: dict[str, str]) -> list[str]:
        return sorted(
            path for path, text in sources.items() if not path.startswith(cls.EXEMPT_TREE) and cls.PATTERN.search(text)
        )


class TestNoSourceNamesMakeInstall:
    def test_nothing_under_src_tells_a_person_to_run_a_make_install_target(self) -> None:
        sources = {_rel(path): _read(path) for path in sorted((_ROOT / "src").rglob("*.py"))}

        assert MakeInstallInSources.naming(sources) == []

    def test_a_source_that_names_the_target_in_any_of_its_spellings_is_caught(self) -> None:
        sources = {
            "src/slice_runner/a.py": 'FIX = "make install-program"',
            "src/slice_runner/b.py": 'FIX = f"make -C {checkout} install-program"',
            "src/slice_runner/c.py": 'FIX = "make   install-tui"',
            "src/slice_runner/d.py": 'FIX = "slice-runner update"',
        }

        assert MakeInstallInSources.naming(sources) == [
            "src/slice_runner/a.py",
            "src/slice_runner/b.py",
            "src/slice_runner/c.py",
        ]

    def test_the_tests_that_assert_the_absence_of_the_target_are_not_the_ones_that_fail_it(self) -> None:
        sources = {"src/slice_runner/tests/infrastructure/test_cli.py": 'assert "make install" not in reported'}

        assert MakeInstallInSources.naming(sources) == []
