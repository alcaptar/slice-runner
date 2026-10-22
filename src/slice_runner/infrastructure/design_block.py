from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.design import Design


class DesignBlock:
    HEADING = "## Diseno"

    @classmethod
    def of(cls, designs: tuple[Design, ...]) -> list[str]:
        if not designs:
            return []

        lines = ["", cls.HEADING]
        for design in designs:
            lines.extend(["", f"### {design.name}", "```html", design.html, "```"])

        return lines
