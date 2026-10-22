from __future__ import annotations

from slice_runner.domain.design import Design
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.tests.mothers.design_mother import DesignMother


class TestTheDesignsOfTheParent:
    @staticmethod
    def _section(*designs: tuple[str, str]) -> str:
        blocks = [
            f'### {name}\n<details>\n<summary><a href="https://example.test/{name}">{name}</a></summary>\n\n'
            f"```html\n{html}\n```\n\n</details>\n"
            for name, html in designs
        ]

        return "## Intencion\nx\n\n## Diseno\n" + "\n".join(blocks) + "\n## Decisiones\n- una decision\n"

    def test_the_html_of_the_first_code_block_under_a_design_heading_is_the_design(self) -> None:
        body = self._section(("tablero", DesignMother.BOARD_HTML))

        parsed = ParentBody.parse(body, repo=None)

        assert parsed.designs == (DesignMother.board(),)

    def test_the_details_the_summary_and_the_link_are_for_the_person_and_do_not_travel(self) -> None:
        body = self._section(("tablero", DesignMother.BOARD_HTML))

        html = ParentBody.parse(body, repo=None).designs[0].html

        assert html == DesignMother.BOARD_HTML

    def test_every_heading_of_the_section_is_its_own_design_in_the_order_it_was_written(self) -> None:
        body = self._section(("tablero", DesignMother.BOARD_HTML), ("detalle", DesignMother.DETAIL_HTML))

        parsed = ParentBody.parse(body, repo=None)

        assert parsed.designs == (DesignMother.board(), DesignMother.detail())

    def test_a_heading_inside_the_section_is_a_design_name_and_never_a_repo(self) -> None:
        body = self._section(("tablero", DesignMother.BOARD_HTML))

        parsed = ParentBody.parse(body, repo="alcaptar/otro-repo")

        assert parsed.designs == (DesignMother.board(),)

    def test_only_the_first_code_block_of_a_design_is_its_html(self) -> None:
        body = "## Diseno\n### tablero\n```html\n<p>uno</p>\n```\n\n```html\n<p>dos</p>\n```\n"

        parsed = ParentBody.parse(body, repo=None)

        assert parsed.designs == (Design(name="tablero", html="<p>uno</p>"),)

    def test_a_multiline_html_keeps_its_lines_untouched(self) -> None:
        html = "<div>\n  <p>uno</p>\n  <p>dos</p>\n</div>"
        body = f"## Diseno\n### tablero\n```html\n{html}\n```\n"

        parsed = ParentBody.parse(body, repo=None)

        assert parsed.designs[0].html == html

    def test_a_body_without_the_section_declares_no_designs(self) -> None:
        parsed = ParentBody.parse("## Intencion\nx\n", repo=None)

        assert parsed.designs == ()

    def test_the_designs_do_not_leak_into_the_sections_around_them(self) -> None:
        body = self._section(("tablero", DesignMother.BOARD_HTML))

        parsed = ParentBody.parse(body, repo=None)

        assert (parsed.intention, parsed.decisions) == ("x", ("una decision",))
