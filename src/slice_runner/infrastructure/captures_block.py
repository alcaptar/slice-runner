from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.design_captures import DesignCaptures

if TYPE_CHECKING:
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures


class CapturesBlock:
    HEADING: ClassVar[str] = "## Capturas del diseno"
    SUPPORT: ClassVar[str] = (
        "Una captura es apoyo y no basta para aprobar: abre cada una con `Read`, contrastala con el HTML del "
        "diseno y con el diff, y no apruebes ni bloquees solo por lo que muestra."
    )

    @classmethod
    def of(cls, captures: DesignCaptures | MissingDesignCaptures) -> list[str]:
        if not isinstance(captures, DesignCaptures):
            return ["", cls.HEADING, "", f"No hay capturas: {captures.reason}"]
        if not captures.captures:
            return []

        return [
            "",
            cls.HEADING,
            "",
            cls.SUPPORT,
            "",
            *(f"- {capture.design} | {capture.state}: {capture.path}" for capture in captures.captures),
        ]
