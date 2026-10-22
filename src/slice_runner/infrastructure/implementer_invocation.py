from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.effort import Effort
from slice_runner.infrastructure.cited_finding import CitedFinding
from slice_runner.infrastructure.cited_sources import CitedSources
from slice_runner.infrastructure.counted_lines import CountedLines
from slice_runner.infrastructure.design_block import DesignBlock
from slice_runner.infrastructure.harness_invocation_runner import HarnessInvocation
from slice_runner.infrastructure.prior_art_block import PriorArtBlock
from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.slice_implementer_brief import SliceImplementerBrief
from slice_runner.infrastructure.tagged_block import TaggedBlock

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.pull_request_review_comment import PullRequestReviewComment
    from slice_runner.domain.requested_change import RequestedChange
    from slice_runner.domain.source_reader import SourceReader


@dataclass(frozen=True, kw_only=True, slots=True)
class ImplementerInvocation(HarnessInvocation):
    EXECUTABLE: ClassVar[str] = "claude"
    MODEL: ClassVar[str] = "claude-sonnet-5-5"
    EFFORT: ClassVar[Effort] = Effort.HIGH

    assignment: Assignment
    reader: SourceReader

    @property
    def cwd(self) -> str:
        return self.assignment.worktree

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--model",
            self.MODEL,
            "--effort",
            str(self.EFFORT),
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(SliceImplementerBrief.TOOLS),
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--json-schema",
            json.dumps(ImplementationReportPayload.json_schema(), ensure_ascii=False),
        ]

    @property
    def text(self) -> str:
        return "\n".join(
            [
                TaggedBlock.of("datos_de_la_slice", self._slice_data),
                "",
                *self._brief,
                *self._retry_instruction,
                *self._requested_changes,
            ]
        )

    @property
    def _brief(self) -> list[str]:
        if not self.assignment.designs:
            return [SliceImplementerBrief.TEXT]

        worktree = self.assignment.worktree

        return [
            SliceImplementerBrief.TEXT,
            SliceImplementerBrief.DESIGN_TEXT,
            SliceImplementerBrief.captures_text(
                directory=DesignCapturesDirectory.of(worktree), manifest=DesignCapturesDirectory.manifest_of(worktree)
            ),
        ]

    @property
    def _slice_data(self) -> str:
        assignment = self.assignment

        return "\n".join(
            [
                f"- issue: #{assignment.issue}",
                f"- slice: {assignment.slice_id}",
                f"- repo: {assignment.repo}",
                f"- ruta del repo: {assignment.worktree}",
                f"- intencion: {assignment.intention}",
                *PriorArtBlock.of(assignment.prior_art),
                f"- senal: {assignment.signal}",
                f"- excluye: {assignment.excludes}",
                f"- sustituye: {assignment.replaces}",
                *CountedLines.of("criterios de aceptacion", assignment.criteria),
                *CitedSources.of(
                    "fuentes de convencion",
                    reader=self.reader,
                    worktree=assignment.worktree,
                    sources=assignment.sources,
                ),
                *self._controls,
                *self._findings,
                *self._control_logs,
                *self._hygiene_refusal,
                *self._dirty_worktree,
                *self._staged_files,
                *self._decisions,
                *DesignBlock.of(assignment.designs),
            ]
        )

    @property
    def _requested_changes(self) -> list[str]:
        changes = self.assignment.requested_changes
        if not changes:
            return []

        return [
            "",
            "## Peticion de cambio en la pull request",
            "",
            "Ya se habia abierto la pull request de esta slice cuando alguien pidio estos cambios en la review;",
            "atiendelos antes de nada mas:",
            "",
            "\n\n".join(self._change_block(change) for change in changes),
        ]

    @classmethod
    def _change_block(cls, change: RequestedChange) -> str:
        parts = [change.body] if change.body.strip() else []
        parts.extend(cls._anchored(comment) for comment in change.comments)

        return "\n\n".join(parts)

    @classmethod
    def _anchored(cls, comment: PullRequestReviewComment) -> str:
        return f"{cls._location(path=comment.path, line=comment.line)}: {comment.body}"

    @property
    def _retry_instruction(self) -> list[str]:
        instruction = self.assignment.retry_instruction.strip()
        if not instruction:
            return []

        return [
            "",
            "## Instruccion de reintento",
            "",
            "Esta slice estaba bloqueada o abortada; una persona la reabrio con esta instruccion, que gana a lo",
            "que hicieras antes del bloqueo:",
            "",
            instruction,
        ]

    @property
    def _decisions(self) -> list[str]:
        decisions = self.assignment.decisions
        if not decisions:
            return []

        return ["", "## Decisiones de diseno", "", *(f"- {decision}" for decision in decisions)]

    @property
    def _controls(self) -> list[str]:
        controls = self.assignment.controls
        if controls.exemption_reason is not None:
            return [f"- controles del repo: ninguno - {controls.exemption_reason}"]

        return CountedLines.of(
            "controles del repo", tuple(f"{control.name}: {control.command}" for control in controls.commands)
        )

    @property
    def _findings(self) -> list[str]:
        findings = self.assignment.findings
        if not findings:
            return ["- hallazgos de la vuelta anterior: ninguno, esta es la primera"]

        return CountedLines.of(
            "hallazgos de la vuelta anterior",
            tuple(CitedFinding.of(finding) for finding in findings),
        )

    @property
    def _control_logs(self) -> list[str]:
        logs = self.assignment.control_logs
        if not logs:
            return []

        return CountedLines.of("logs de los controles en rojo", tuple(str(log) for log in logs))

    @property
    def _hygiene_refusal(self) -> list[str]:
        refusal = self.assignment.hygiene_refusal
        if not refusal:
            return []

        return [
            "- la vuelta anterior no llego a medirse: el indice quedo sucio y los controles no se ejecutaron",
            f"  - {refusal}",
            "  - declara en tu informe TODO fichero que toques, o no lo toques",
        ]

    @property
    def _dirty_worktree(self) -> list[str]:
        files = self.assignment.dirty_worktree_files
        if not files:
            return []

        return [
            "- la vuelta anterior murio sin informe legible: el arbol de trabajo puede traer ediciones o borrados "
            "que nadie declaro",
            *(f"  - {path}" for path in files),
        ]

    @property
    def _staged_files(self) -> list[str]:
        files = self.assignment.staged_files
        if not files:
            return []

        return [
            "- ficheros ya en el indice:",
            *(f"  - {path}" for path in files),
            "  - estan en el indice y no los puedes sacar: declaralos todos en tu informe",
        ]

    @staticmethod
    def _location(*, path: str, line: int | None) -> str:
        return f"{path}:{line}" if line is not None else path
