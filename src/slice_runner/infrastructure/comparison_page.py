from __future__ import annotations

import html
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.design_captures import DesignCaptures

if TYPE_CHECKING:
    from collections.abc import Mapping

    from slice_runner.domain.design import Design
    from slice_runner.domain.design_capture import DesignCapture
    from slice_runner.domain.missing_design_captures import MissingDesignCaptures


class ComparisonPage:
    HTML_CAPTURE_SUFFIX: ClassVar[str] = ".html"
    STYLE: ClassVar[str] = (
        "body{font-family:sans-serif;margin:1rem}"
        ".pair{display:flex;gap:1rem;margin-bottom:2rem}"
        ".pair>div{flex:1}"
        "iframe{width:100%;height:30rem;border:1px solid #888}"
        "img{max-width:100%}"
    )

    @classmethod
    def of(
        cls,
        *,
        designs: tuple[Design, ...],
        captures: DesignCaptures | MissingDesignCaptures,
        contents: Mapping[str, str],
    ) -> str:
        if isinstance(captures, DesignCaptures):
            by_name = {design.name: design for design in designs}
            pairs = [cls._pair(by_name[capture.design], capture, contents) for capture in captures.captures]
        else:
            pairs = [cls._unavailable(design, captures.reason) for design in designs]

        return (
            '<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Design comparison</title>'
            f"<style>{cls.STYLE}</style></head><body>\n" + "\n".join(pairs) + "\n</body></html>\n"
        )

    @classmethod
    def _pair(cls, design: Design, capture: DesignCapture, contents: Mapping[str, str]) -> str:
        return cls._section(design, f"<p>{html.escape(capture.state)}</p>{cls._shown(capture, contents)}")

    @classmethod
    def _unavailable(cls, design: Design, reason: str) -> str:
        return cls._section(design, f"<p>No capture: {html.escape(reason)}</p>")

    @classmethod
    def _section(cls, design: Design, other_side: str) -> str:
        return (
            '<section class="pair">'
            f"<div><h2>{html.escape(design.name)}</h2>{cls._frame(design.html)}</div>"
            f"<div>{other_side}</div>"
            "</section>"
        )

    @classmethod
    def _shown(cls, capture: DesignCapture, contents: Mapping[str, str]) -> str:
        if capture.path.endswith(cls.HTML_CAPTURE_SUFFIX):
            return cls._frame(contents[capture.path])

        return f'<img src="{html.escape(PurePosixPath(capture.path).name)}" alt="{html.escape(capture.state)}">'

    @staticmethod
    def _frame(content: str) -> str:
        return f'<iframe srcdoc="{html.escape(content, quote=True)}"></iframe>'
