from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.infrastructure.automation_mark import AutomationMark

if TYPE_CHECKING:
    from datetime import datetime


class ResetComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:reseteada -->"

    @classmethod
    def rendered(cls, *, branch: str, at: datetime) -> str:
        return "\n\n".join(
            [
                f"Slice reseteada a `estado:pendiente` el {at.isoformat()}. Ni la rama `{branch}` ni el arbol de "
                "trabajo se han tocado: decidir si limpiarlos es de una persona.",
                cls.MARKER,
                AutomationMark.TEXT,
            ]
        )
