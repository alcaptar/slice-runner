from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.retired_issue_label import RetiredIssueLabel
    from slice_runner.domain.run import Run

_PARENT_BODY_WITHOUT_DECISIONS = (
    "## Intencion\n"
    "hoy conducir una slice todavia exige una sesion de chat.\n"
    "\n"
    "## Fuentes de convencion\n"
    "- doc: CLAUDE.md\n"
    "\n"
    "## Controles\n"
    "- lint: make linting\n"
)

_PARENT_BODY = f"{_PARENT_BODY_WITHOUT_DECISIONS}\n## Decisiones\n- el conductor no compone telemetria\n"

_SUBISSUE_PROSE_WITHOUT_DECISIONS = (
    "INTENCION: hoy nada evita reimplementar una slice ya entregada\n"
    "ACEPTACION: el run retoma por el paso que dice el estado persistido\n"
    "SENAL: exenta - este repo no despliega\n"
)

_SUBISSUE_PROSE = f"DECISION: el estado persistido manda sobre la rama\n{_SUBISSUE_PROSE_WITHOUT_DECISIONS}"


class GhConversationMother:
    REPO: ClassVar[str] = "alcaptar/slice-runner"
    ROOT: ClassVar[str] = "/repos/slice-runner"
    WORKTREE: ClassVar[str] = "/repos/slice-runner/.worktrees/05-prechecks-deterministas"
    BASE: ClassVar[str] = "master"
    ISSUE: ClassVar[int] = 38
    SUBISSUE: ClassVar[int] = 45
    SLICE: ClassVar[str] = "slice-05"
    NAME: ClassVar[str] = "prechecks-deterministas"
    SUMMARY: ClassVar[str] = "comprobar antes de tocar codigo"
    BRANCH: ClassVar[str] = "slice/05-prechecks-deterministas"
    PULL_REQUEST: ClassVar[int] = 61
    CONTROL: ClassVar[str] = "make linting"
    OTHER_SUBISSUE: ClassVar[int] = 46
    OTHER_SLICE: ClassVar[str] = "slice-06"
    OTHER_NAME: ClassVar[str] = "pausa-de-alineacion"
    OTHER_SUMMARY: ClassVar[str] = "el entendimiento se escribe siempre"
    OTHER_BRANCH: ClassVar[str] = "slice/06-pausa-de-alineacion"

    @classmethod
    def parent_of_one_slice(cls) -> str:
        return json.dumps(
            {
                "body": _PARENT_BODY,
                "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1},
                "state": IssueState.OPEN.value,
            }
        )

    @classmethod
    def parent_of_one_slice_without_decisions(cls) -> str:
        return json.dumps(
            {
                "body": _PARENT_BODY_WITHOUT_DECISIONS,
                "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1},
                "state": IssueState.OPEN.value,
            }
        )

    @classmethod
    def parent_of_two_slices(cls) -> str:
        return json.dumps(
            {
                "body": _PARENT_BODY,
                "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 2},
                "state": IssueState.OPEN.value,
            }
        )

    @classmethod
    def body_of_the_subissue(cls) -> str:
        return json.dumps({"body": _SUBISSUE_PROSE})

    @classmethod
    def the_slice_resumed_at(cls, run: Run, *, label: IssueLabel | RetiredIssueLabel = IssueLabel.IN_PROGRESS) -> str:
        return cls._children(body=f"{_SUBISSUE_PROSE}\n{cls._state_block(run)}\n", label=label, state=IssueState.OPEN)

    @classmethod
    def the_subissue_viewed(cls, *, label: IssueLabel | RetiredIssueLabel, run: Run | None = None) -> dict[str, object]:
        block = cls._state_block(run) if run is not None else ""
        body = f"{_SUBISSUE_PROSE}\n{block}\n"

        return cls._entry(
            number=cls.SUBISSUE,
            slice_id=cls.SLICE,
            name=cls.NAME,
            summary=cls.SUMMARY,
            body=body,
            label=label,
            state=IssueState.OPEN,
        )

    @classmethod
    def the_slice_never_run(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE, label=IssueLabel.PENDING, state=IssueState.OPEN)

    @classmethod
    def the_slice_never_run_without_decisions(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE_WITHOUT_DECISIONS, label=IssueLabel.PENDING, state=IssueState.OPEN)

    @classmethod
    def the_slice_aborted_before_touching_code(cls) -> str:
        return cls._children(
            body=f"{_SUBISSUE_PROSE}\n{cls._state_block(RunMother.aborted_before_touching_code())}\n",
            label=IssueLabel.ABORTED_BUDGET,
            state=IssueState.OPEN,
        )

    @classmethod
    def the_slice_marked_in_progress_that_never_persisted_a_run(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE, label=IssueLabel.IN_PROGRESS, state=IssueState.OPEN)

    @classmethod
    def the_comments_of_a_person_typing(cls, body: str) -> str:
        return json.dumps({"comments": [{"body": body}]})

    @classmethod
    def the_slice_already_closed(cls) -> str:
        return cls._children(body=_SUBISSUE_PROSE, label=IssueLabel.PENDING, state=IssueState.CLOSED)

    @classmethod
    def two_slices_resumed_at(
        cls, run: Run, *, second_label: IssueLabel | RetiredIssueLabel = IssueLabel.IN_PROGRESS
    ) -> str:
        body = f"{_SUBISSUE_PROSE}\n{cls._state_block(run)}\n"
        return json.dumps(
            [
                cls._entry(
                    number=cls.SUBISSUE,
                    slice_id=cls.SLICE,
                    name=cls.NAME,
                    summary=cls.SUMMARY,
                    body=body,
                    label=IssueLabel.IN_PROGRESS,
                    state=IssueState.OPEN,
                ),
                cls._entry(
                    number=cls.OTHER_SUBISSUE,
                    slice_id=cls.OTHER_SLICE,
                    name=cls.OTHER_NAME,
                    summary=cls.OTHER_SUMMARY,
                    body=body,
                    label=second_label,
                    state=IssueState.OPEN,
                ),
            ]
        )

    @classmethod
    def a_title_that_names_no_slice(cls) -> str:
        return json.dumps(
            [
                {
                    "number": cls.SUBISSUE,
                    "title": "una subissue que nadie titulo como slice",
                    "body": _SUBISSUE_PROSE,
                    "labels": [],
                    "state": IssueState.OPEN.value,
                }
            ]
        )

    @classmethod
    def no_open_pull_request(cls) -> str:
        return json.dumps([])

    @classmethod
    def the_open_pull_request(cls) -> str:
        return json.dumps([{"number": cls.PULL_REQUEST}])

    @classmethod
    def the_pull_request_of_the_branch(cls) -> str:
        return json.dumps([{"number": cls.PULL_REQUEST}])

    @classmethod
    def a_merged_pull_request(cls) -> str:
        return json.dumps({"state": "MERGED", "mergeable": "MERGEABLE"})

    @classmethod
    def a_pull_request_still_open(cls) -> str:
        return json.dumps({"state": "OPEN", "mergeable": "MERGEABLE"})

    @classmethod
    def a_pull_request_closed_without_merging(cls) -> str:
        return json.dumps({"state": "CLOSED", "mergeable": "UNKNOWN"})

    @classmethod
    def a_pull_request_in_conflict_with_its_base(cls) -> str:
        return json.dumps({"state": "OPEN", "mergeable": "CONFLICTING"})

    @classmethod
    def checks_in_red(cls) -> str:
        return json.dumps([{"name": "check", "bucket": "fail"}])

    @classmethod
    def _children(cls, *, body: str, label: IssueLabel | RetiredIssueLabel, state: IssueState) -> str:
        return json.dumps(
            [
                cls._entry(
                    number=cls.SUBISSUE,
                    slice_id=cls.SLICE,
                    name=cls.NAME,
                    summary=cls.SUMMARY,
                    body=body,
                    label=label,
                    state=state,
                )
            ]
        )

    @staticmethod
    def _entry(
        *,
        number: int,
        slice_id: str,
        name: str,
        summary: str,
        body: str,
        label: IssueLabel | RetiredIssueLabel,
        state: IssueState,
    ) -> dict[str, object]:
        return {
            "number": number,
            "title": f"{slice_id} ({name}): {summary}",
            "body": body,
            "labels": [{"id": "LA_kwDOThEBoM8AAAACu6gVcw", "name": label.value, "description": "", "color": "1d76db"}],
            "state": state.value,
        }

    @staticmethod
    def _state_block(run: Run) -> str:
        state = {
            "step": run.step.value,
            "retry_instruction": run.retry_instruction,
            "control_retries": run.control_retries,
            "hygiene_retries": run.hygiene_retries,
            "verify_retries": run.verify_retries,
            "ci_retries": run.ci_retries,
            "indeterminate_ticks": run.indeterminate_ticks,
            "verify_discards": run.verify_discards,
            "control_rounds_logged": run.control_rounds_logged,
            "verify_rounds_logged": run.verify_rounds_logged,
            "tree_unexpected": run.tree_unexpected,
        }

        return f"<!-- slice-runner:estado\n{json.dumps(state)}\n-->"
