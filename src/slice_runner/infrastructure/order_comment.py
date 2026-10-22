from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.automation_mark import AutomationMark

if TYPE_CHECKING:
    from slice_runner.domain.order import Order


class OrderComment:
    @classmethod
    def rendered(cls, order: Order, text: str) -> str:
        return "\n\n".join([cls._statement(order, text), AutomationMark.TEXT])

    @staticmethod
    def _statement(order: Order, text: str) -> str:
        if not text:
            return f"Orden `{order}` dada con `slice-runner`."

        return f"Orden `{order}` dada con `slice-runner`, con este texto:\n\n{text}"
