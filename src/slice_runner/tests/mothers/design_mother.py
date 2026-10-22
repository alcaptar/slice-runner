from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.design import Design


class DesignMother:
    BOARD_HTML: ClassVar[str] = '<div class="board" style="color:#112233">Tablero de slices</div>'
    DETAIL_HTML: ClassVar[str] = '<section class="detail" style="color:#445566">Detalle de la slice</section>'

    @classmethod
    def board(cls) -> Design:
        return Design(name="tablero", html=cls.BOARD_HTML)

    @classmethod
    def detail(cls) -> Design:
        return Design(name="detalle", html=cls.DETAIL_HTML)
