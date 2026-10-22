from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import UnreadableFindingsError
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.published_finding_payload import PublishedFindingPayload

if TYPE_CHECKING:
    from slice_runner.domain.declared_debt import DeclaredDebt
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.findings_history import FindingsHistory, GroupedFinding


class VetoFindingsComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:hallazgos -->"
    _BLOCK: ClassVar[re.Pattern[str]] = re.compile(r"<!-- slice-runner:hallazgos-json\n(.*?)\n-->", re.DOTALL)

    @classmethod
    def rendered(cls, history: FindingsHistory, debt: DeclaredDebt) -> str:
        numbered = tuple(enumerate(history.entries, start=1))
        standing = tuple(
            (index, entry) for index, entry in numbered if entry.seen_in_the_last_round(history.last_round)
        )
        not_standing = tuple(
            (index, entry) for index, entry in numbered if not entry.seen_in_the_last_round(history.last_round)
        )

        sections = [cls._header(history)]
        if standing:
            sections.append(cls._section("Hallazgos vigentes tras la ultima ronda", standing))
        if not_standing:
            sections.append(
                cls._section("Hallazgos de rondas anteriores que no reaparecieron en la ultima ronda", not_standing)
            )
        if debt.left_out:
            sections.append(cls._left_out(debt))
        sections.append(cls._block(numbered))
        sections.append(cls.MARKER)
        sections.append(AutomationMark.TEXT)

        return "\n\n".join(sections)

    @classmethod
    def is_the_veto_findings(cls, body: str) -> bool:
        return cls.MARKER in body

    @classmethod
    def finding_of(cls, body: str, finding_id: str) -> Finding | None:
        for published in cls._decoded(body):
            if published.id == finding_id:
                return published.to_domain()

        return None

    @staticmethod
    def _header(history: FindingsHistory) -> str:
        return (
            f"Este veto reune los hallazgos de {history.composed_rounds} ronda(s) de esta slice, "
            f"con {len(history.entries)} hallazgo(s) tras agrupar."
        )

    @classmethod
    def _section(cls, title: str, entries: tuple[tuple[int, GroupedFinding], ...]) -> str:
        lines = [f"## {title}"]
        for index, entry in entries:
            lines.append(cls._entry_header(index, entry))
            lines.extend(cls._evidence_lines(entry))

        return "\n".join(lines)

    @staticmethod
    def _entry_header(index: int, entry: GroupedFinding) -> str:
        last = entry.last_appearance.finding

        return f"- `f{index}` {last.severity}: {last.rule} - {last.detail} ({last.path})"

    @staticmethod
    def _evidence_lines(entry: GroupedFinding) -> list[str]:
        return [
            f"  - ronda {appearance.round} ({appearance.finding.severity}): {appearance.finding.evidence}"
            for appearance in entry.appearances
        ]

    @staticmethod
    def _left_out(debt: DeclaredDebt) -> str:
        return "\n".join(
            ["## Lo que declaro el implementador haber dejado fuera", *(f"- {item}" for item in debt.left_out)]
        )

    @classmethod
    def _block(cls, numbered: tuple[tuple[int, GroupedFinding], ...]) -> str:
        payload = [item for index, entry in numbered for item in cls._payloads_of(index, entry)]

        return f"<!-- slice-runner:hallazgos-json\n{json.dumps(payload, ensure_ascii=False)}\n-->"

    @staticmethod
    def _payloads_of(index: int, entry: GroupedFinding) -> list[dict[str, object]]:
        displayed = entry.last_appearance
        others = tuple(appearance for appearance in entry.appearances if appearance is not displayed)

        return [
            PublishedFindingPayload.from_domain(id=f"f{index}", finding=displayed.finding).to_contract(),
            *(
                PublishedFindingPayload.from_domain(id=f"f{index}-{position}", finding=appearance.finding).to_contract()
                for position, appearance in enumerate(others, start=1)
            ),
        ]

    @classmethod
    def _decoded(cls, body: str) -> tuple[PublishedFindingPayload, ...]:
        found = cls._BLOCK.search(body)
        if not found:
            return ()

        try:
            data = json.loads(found.group(1))
        except json.JSONDecodeError as error:
            raise UnreadableFindingsError(f"the veto findings block is not valid JSON: {error}") from error
        if not isinstance(data, list):
            raise UnreadableFindingsError(f"the veto findings block has to be an array, not {type(data).__name__}")

        return tuple(PublishedFindingPayload.from_dict(item) for item in data)
