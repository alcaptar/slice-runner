from __future__ import annotations

from slice_runner.infrastructure.automation_mark import AutomationMark


class CatchUpConflictComment:
    @classmethod
    def rendered(cls, paths: tuple[str, ...]) -> str:
        return "\n\n".join(
            [
                "La puesta al dia de la rama con su base no pudo fusionar sola. Los ficheros en conflicto son:",
                "\n".join(f"- `{path}`" for path in paths),
                AutomationMark.TEXT,
            ]
        )
