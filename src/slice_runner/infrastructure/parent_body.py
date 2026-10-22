from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.control_command import ControlCommand
from slice_runner.domain.controls import Controls
from slice_runner.domain.design import Design
from slice_runner.domain.exceptions import MalformedConventionLineError
from slice_runner.domain.source import Source, SourceKind

if TYPE_CHECKING:
    from collections.abc import Iterator

_CONTROLS_EXEMPTION = "ninguno"
_INTENTION_HEADING = re.compile(r"^\s*##\s+intenci[oó]n\s*$", re.IGNORECASE)
_PRIOR_ART_HEADING = re.compile(r"^\s*##\s+lo\s+que\s+ya\s+existe\s*$", re.IGNORECASE)
_SOURCES_HEADING = re.compile(r"^\s*##\s+fuentes\s+de\s+convenci[oó]n\s*$", re.IGNORECASE)
_DECISIONS_HEADING = re.compile(r"^\s*##\s+decisiones\s*$", re.IGNORECASE)
_DECISION_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")
_DESIGN_HEADING = re.compile(r"^\s*##\s+dise[nñ]o\s*$", re.IGNORECASE)
_FENCE = re.compile(r"^\s*```")
_CONTROLS_HEADING = re.compile(r"^\s*##\s+controles\s*$", re.IGNORECASE)
_H2 = re.compile(r"^\s*##\s+")
_SUBHEADING = re.compile(r"^\s*###\s+(.+?)\s*$")
_SOURCE_LINE = re.compile(r"^\s*-\s*(doc|skill)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_CONTROL_LINE = re.compile(r"^\s*-\s*([\w-]+)\s*:\s*(.+?)\s*$")


@dataclass(frozen=True, kw_only=True, slots=True)
class ParsedParentBody:
    intention: str
    prior_art: str
    decisions: tuple[str, ...]
    sources: tuple[Source, ...]
    controls: Controls
    designs: tuple[Design, ...]


class ParentBody:
    @classmethod
    def parse(cls, body: str, *, repo: str | None) -> ParsedParentBody:
        return ParsedParentBody(
            intention=cls._section_text(body, _INTENTION_HEADING),
            prior_art=cls._section_text(body, _PRIOR_ART_HEADING),
            decisions=cls._decisions(body),
            sources=cls._sources(body, repo),
            controls=cls._controls(body, repo),
            designs=cls._designs(body),
        )

    @staticmethod
    def _section_text(body: str, heading: re.Pattern[str]) -> str:
        collected: list[str] = []
        in_section = False
        for line in body.splitlines():
            if heading.match(line):
                in_section = True
                continue
            if in_section:
                if _H2.match(line):
                    break
                collected.append(line)

        return "\n".join(collected).strip()

    @classmethod
    def _decisions(cls, body: str) -> tuple[str, ...]:
        items = (_DECISION_ITEM.match(line) for line in cls._section_text(body, _DECISIONS_HEADING).splitlines())

        return tuple(item.group(1) for item in items if item)

    @classmethod
    def _designs(cls, body: str) -> tuple[Design, ...]:
        designs: list[Design] = []
        name: str | None = None
        html: list[str] | None = None
        fenced = False
        in_section = False
        for line in body.splitlines():
            if not in_section:
                in_section = bool(_DESIGN_HEADING.match(line))
                continue
            if fenced:
                if _FENCE.match(line):
                    fenced = False
                    if name is not None and html is not None:
                        designs.append(Design(name=name, html="\n".join(html)))
                        name, html = None, None
                elif html is not None:
                    html.append(line)
                continue
            if _H2.match(line):
                break
            if sub := _SUBHEADING.match(line):
                name, html = sub.group(1), None
            elif _FENCE.match(line):
                fenced = True
                html = [] if name is not None and html is None else None

        return tuple(designs)

    @classmethod
    def _sources(cls, body: str, repo: str | None) -> tuple[Source, ...]:
        sources: list[Source] = []
        for owner, line in cls._repo_scoped_lines(body, _SOURCES_HEADING):
            if owner != repo:
                continue
            if m := _SOURCE_LINE.match(line):
                sources.append(Source(kind=SourceKind(m.group(1).lower()), path=m.group(2).strip()))
            elif cls._looks_like_an_item(line):
                raise MalformedConventionLineError(
                    f"a line under `## Fuentes de convencion` looks like a source but cannot be read as one: {line!r}"
                )

        return tuple(sources)

    @classmethod
    def _controls(cls, body: str, repo: str | None) -> Controls:
        commands: list[ControlCommand] = []
        exemption_reason: str | None = None
        for name, value in cls._control_pairs(body, repo):
            if name.lower() == _CONTROLS_EXEMPTION:
                exemption_reason = value
            else:
                commands.append(ControlCommand(name=name, command=value))

        if commands and exemption_reason is not None:
            raise MalformedConventionLineError(
                f"the reserved `{_CONTROLS_EXEMPTION}` line and the controls "
                f"{[command.name for command in commands]} cannot both hold for the same repo"
            )

        return Controls(commands=tuple(commands), exemption_reason=exemption_reason)

    @classmethod
    def _control_pairs(cls, body: str, repo: str | None) -> Iterator[tuple[str, str]]:
        for owner, line in cls._repo_scoped_lines(body, _CONTROLS_HEADING):
            if owner != repo:
                continue
            if m := _CONTROL_LINE.match(line):
                yield m.group(1).strip(), m.group(2).strip()
            elif cls._looks_like_an_item(line):
                raise MalformedConventionLineError(
                    f"a line under `## Controles` looks like a control but cannot be read as one: {line!r}"
                )

    @staticmethod
    def _looks_like_an_item(line: str) -> bool:
        return line.strip().startswith("-")

    @staticmethod
    def _repo_scoped_lines(body: str, heading: re.Pattern[str]) -> Iterator[tuple[str | None, str]]:
        in_section = False
        owner: str | None = None
        for line in body.splitlines():
            if heading.match(line):
                in_section = True
                owner = None
                continue
            if not in_section:
                continue
            if _H2.match(line):
                break
            if sub := _SUBHEADING.match(line):
                owner = sub.group(1)
                continue
            yield owner, line
