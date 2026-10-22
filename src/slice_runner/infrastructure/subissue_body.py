from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import EmptyIssueBodyError, UnreadableRunError
from slice_runner.infrastructure.run_payload import RunPayload

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO_LINE = re.compile(r"^REPO\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_INTENTION_LINE = re.compile(r"^INTENCION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_CRITERION_LINE = re.compile(r"^ACEPTACION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_DECISION_LINE = re.compile(r"^DECISION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_SIGNAL_LINE = re.compile(r"^SENAL\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_EXCLUDES_LINE = re.compile(r"^EXCLUYE\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_REPLACES_LINE = re.compile(r"^SUSTITUYE\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_DESIGN_LINE = re.compile(r"^DISENO\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_STATE_BLOCK = re.compile(r"<!-- slice-runner:estado\n(.*?)\n-->", re.DOTALL)


@dataclass(frozen=True, kw_only=True, slots=True)
class ParsedSubissueBody:
    repo: str | None
    intention: str
    criteria: tuple[str, ...]
    decisions: tuple[str, ...]
    signal: str
    excludes: str
    replaces: str
    designs: tuple[str, ...]
    run: Run | None


class SubissueBody:
    @classmethod
    def parse(cls, body: str) -> ParsedSubissueBody:
        return ParsedSubissueBody(
            repo=cls._first(_REPO_LINE, body),
            intention=cls._first(_INTENTION_LINE, body) or "",
            criteria=tuple(_CRITERION_LINE.findall(body)),
            decisions=tuple(_DECISION_LINE.findall(body)),
            signal=cls._first(_SIGNAL_LINE, body) or "",
            excludes=cls._first(_EXCLUDES_LINE, body) or "",
            replaces=cls._first(_REPLACES_LINE, body) or "",
            designs=tuple(_DESIGN_LINE.findall(body)),
            run=cls._run(body),
        )

    @classmethod
    def with_run(cls, body: str, run: Run) -> str:
        if not body.strip():
            raise EmptyIssueBodyError("the issue body came back empty: there is no prose to derive a write from")

        block = cls._render_block(run)
        if _STATE_BLOCK.search(body):
            return _STATE_BLOCK.sub(lambda _: block, body, count=1)

        prose = body.rstrip("\n")

        return f"{prose}\n\n{block}\n"

    @classmethod
    def without_run(cls, body: str) -> str:
        return _STATE_BLOCK.sub("", body, count=1)

    @staticmethod
    def _first(line: re.Pattern[str], body: str) -> str | None:
        found = line.search(body)

        return found.group(1) if found else None

    @staticmethod
    def _run(body: str) -> Run | None:
        found = _STATE_BLOCK.search(body)
        if not found:
            return None

        try:
            data = json.loads(found.group(1))
        except json.JSONDecodeError as error:
            raise UnreadableRunError(f"the execution state block is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableRunError(f"the execution state block has to be an object, not {type(data).__name__}")

        return RunPayload.from_dict(data).to_domain()

    @staticmethod
    def _render_block(run: Run) -> str:
        payload = json.dumps(RunPayload.from_domain(run).to_contract(), ensure_ascii=False)

        return f"<!-- slice-runner:estado\n{payload}\n-->"
