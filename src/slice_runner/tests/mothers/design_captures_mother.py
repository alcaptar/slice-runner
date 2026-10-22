from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.design_capture import DesignCapture
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.missing_design_captures import MissingDesignCaptures


class DesignCapturesMother:
    BOARD_PATH: ClassVar[str] = "/repos/project/.design-captures/tablero.png"
    DETAIL_PATH: ClassVar[str] = "/repos/project/.design-captures/detalle.png"
    REASON: ClassVar[str] = "no terminal to draw the screen"

    @staticmethod
    def none() -> DesignCaptures:
        return DesignCaptures(captures=())

    @classmethod
    def of_the_board_and_the_detail(cls) -> DesignCaptures:
        return DesignCaptures(
            captures=(
                DesignCapture(design="tablero", state="80 columns, two slices running", path=cls.BOARD_PATH),
                DesignCapture(design="detalle", state="one slice with a finding", path=cls.DETAIL_PATH),
            )
        )

    @classmethod
    def missing(cls) -> MissingDesignCaptures:
        return MissingDesignCaptures(reason=cls.REASON)
