from __future__ import annotations

from slice_runner.domain.readiness import Readiness
from slice_runner.infrastructure.readiness_report import ReadinessReport
from slice_runner.tests.mothers.readiness_check_mother import ReadinessCheckMother


class TestReadinessReport:
    def test_every_check_appears_on_its_own_line_with_its_verdict_and_detail(self) -> None:
        readiness = Readiness(
            checks=(
                ReadinessCheckMother.ready(name="git", detail="2.51.0"),
                ReadinessCheckMother.ready(name="claude", detail="2.1.4"),
            )
        )

        rendered = ReadinessReport(readiness=readiness).rendered()

        assert "git" in rendered
        assert "2.51.0" in rendered
        assert "claude" in rendered
        assert "2.1.4" in rendered
        assert len(rendered.splitlines()) == 2

    def test_a_missing_check_prints_its_fix_command_on_the_line_right_after_it(self) -> None:
        readiness = Readiness(
            checks=(ReadinessCheckMother.missing(name="gh", detail="not authenticated", fix="gh auth login"),)
        )

        lines = ReadinessReport(readiness=readiness).rendered().splitlines()

        assert len(lines) == 2
        assert "gh" in lines[0]
        assert "not authenticated" in lines[0]
        assert lines[1].strip() == "gh auth login"

    def test_a_ready_check_prints_no_second_line_because_there_is_nothing_to_fix(self) -> None:
        rendered = ReadinessReport(readiness=Readiness(checks=(ReadinessCheckMother.ready(),))).rendered()

        assert len(rendered.splitlines()) == 1

    def test_the_verdict_word_of_each_check_is_printed_in_english(self) -> None:
        readiness = Readiness(checks=(ReadinessCheckMother.ready(), ReadinessCheckMother.missing()))

        rendered = ReadinessReport(readiness=readiness).rendered()

        assert "ready" in rendered
        assert "missing" in rendered

    def test_a_warning_prints_its_own_verdict_word_and_its_fix_on_the_line_right_after_it(self) -> None:
        readiness = Readiness(
            checks=(ReadinessCheckMother.warning(detail="master is 1 commit(s) behind its remote", fix="git fetch"),)
        )

        lines = ReadinessReport(readiness=readiness).rendered().splitlines()

        assert "warning" in lines[0]
        assert lines[1].strip() == "git fetch"

    def test_an_unknown_check_prints_its_own_verdict_word_and_no_fix_line(self) -> None:
        readiness = Readiness(checks=(ReadinessCheckMother.unknown(),))

        lines = ReadinessReport(readiness=readiness).rendered().splitlines()

        assert len(lines) == 1
        assert "unknown" in lines[0]
