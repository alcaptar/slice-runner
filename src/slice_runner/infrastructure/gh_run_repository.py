from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import LaggingSearchIndexError, RetiredLabelError, UnreadableIssueError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.parent_issue import ParentIssue
from slice_runner.domain.retired_issue_label import RetiredIssueLabel
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.domain.sub_issue import SubIssue
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.catch_up_conflict_comment import CatchUpConflictComment
from slice_runner.infrastructure.gh_body_payload import GhBodyPayload
from slice_runner.infrastructure.gh_comments_payload import GhCommentPayload, GhCommentsPayload
from slice_runner.infrastructure.gh_parent_view_payload import GhParentViewPayload
from slice_runner.infrastructure.gh_sub_issue_payload import GhSubIssuePayload
from slice_runner.infrastructure.kept_worktree_comment import KeptWorktreeComment
from slice_runner.infrastructure.order_comment import OrderComment
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.reset_comment import ResetComment
from slice_runner.infrastructure.subissue_body import SubissueBody
from slice_runner.infrastructure.veto_findings_comment import VetoFindingsComment

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.declared_debt import DeclaredDebt
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.findings_history import FindingsHistory
    from slice_runner.domain.order import Order
    from slice_runner.domain.precheck_outcome import PrecheckOutcome
    from slice_runner.domain.run import Run
    from slice_runner.domain.worktree_retirement import WorktreeRetirement
    from slice_runner.infrastructure.gh_call import GhCall
    from slice_runner.infrastructure.gh_sub_issue_payload import GhLabelPayload
    from slice_runner.infrastructure.process import ProcessOutput

_LABEL_MISSING = re.compile(r"'(.+?)' not found")
_LABEL_COLOR = "5319e7"
_LABEL_DESCRIPTION = "estado de una slice, escrito por slice-runner"


class GhCommandFailedError(OSError):
    pass


class GhRunRepository(RunRepository):
    SLICE_HEADING: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:(?P<key>[A-Z][A-Z0-9]*-\d+)\s+)?slice-(?P<ordinal>\d{2,})\s*\((?P<name>[^)]+)\)\s*:\s*(?P<summary>.+?)\s*$"
    )

    def __init__(self, *, call: GhCall) -> None:
        self._call = call

    def read_parent(self, *, repo: str, issue: int, slice_repo: str | None) -> ParentIssue:
        output = self._run(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body,subIssuesSummary,state"],
            safe_to_repeat=True,
        )
        payload = GhParentViewPayload.from_dict(self._decoded_object(output))
        parsed = ParentBody.parse(payload.body, repo=slice_repo)

        return ParentIssue(
            intention=parsed.intention,
            prior_art=parsed.prior_art,
            decisions=parsed.decisions,
            sources=parsed.sources,
            controls=parsed.controls,
            designs=parsed.designs,
            subissue_count=payload.subissues_summary.total,
            state=payload.state,
        )

    def read_children(self, *, repo: str, parent: int, expected: int) -> tuple[SubIssue, ...]:
        search = f"parent-issue:{repo}#{parent}"
        output = self._run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--search",
                search,
                "--state",
                "all",
                "--json",
                "number,title,body,labels,state",
            ],
            safe_to_repeat=True,
        )
        items = self._decoded_array(output)
        children = tuple(self._sub_issue_from(GhSubIssuePayload.from_dict(item)) for item in items)
        if len(children) < expected:
            raise LaggingSearchIndexError(
                f"the search index for {repo}#{parent} returned {len(children)} subissue(s), "
                f"the graph knows about {expected}"
            )

        return tuple(sorted(children, key=self._slice_number))

    def read_subissue(self, *, repo: str, issue: int) -> SubIssue:
        output = self._run(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "number,title,body,labels,state"],
            safe_to_repeat=True,
        )

        return self._sub_issue_from(GhSubIssuePayload.from_dict(self._decoded_object(output)))

    def write_run(self, *, repo: str, issue: int, run: Run) -> None:
        current = self._current_body(repo=repo, issue=issue)
        self._write_body_if_changed(
            repo=repo, issue=issue, current=current, updated=SubissueBody.with_run(current, run)
        )

    def clear_run(self, *, repo: str, issue: int) -> None:
        current = self._current_body(repo=repo, issue=issue)
        self._write_body_if_changed(repo=repo, issue=issue, current=current, updated=SubissueBody.without_run(current))

    def _current_body(self, *, repo: str, issue: int) -> str:
        return GhBodyPayload.from_dict(
            self._decoded_object(
                self._run(["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body"], safe_to_repeat=True)
            )
        ).body

    def _write_body_if_changed(self, *, repo: str, issue: int, current: str, updated: str) -> None:
        if updated == current:
            return

        self._run(
            ["gh", "issue", "edit", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=updated,
            safe_to_repeat=True,
        )

    def mark_order(self, *, repo: str, issue: int, order: Order, text: str) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=OrderComment.rendered(order, text),
            safe_to_repeat=False,
        )

    def mark_reset(self, *, repo: str, issue: int, branch: str, at: datetime) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=ResetComment.rendered(branch=branch, at=at),
            safe_to_repeat=False,
        )

    def _comment_bodies(self, *, repo: str, issue: int) -> tuple[str, ...]:
        output = self._run(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments"], safe_to_repeat=True
        )
        payload = GhCommentsPayload.from_dict(self._decoded_object(output))

        return tuple(GhCommentPayload.from_dict(comment).body for comment in payload.comments)

    def write_label(self, *, repo: str, issue: int, remove: IssueLabel | None, add: IssueLabel) -> None:
        argv = self._edit_of(repo=repo, issue=issue, add=add, remove=remove)
        self._edit_with_label_fallback(argv, repo=repo, issue=issue, add=add)

    def remove_label(self, *, repo: str, issue: int, remove: IssueLabel) -> None:
        self._run(
            ["gh", "issue", "edit", str(issue), "--repo", repo, "--remove-label", remove.value], safe_to_repeat=True
        )

    def flag_unmerged_pull_request(self, *, repo: str, issue: int, pull_request: int) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=AutomationMark.appended_to(
                f"La espera del merge se agoto con la pull request #{pull_request} sin fusionar. Si esta en "
                "borrador, sacala: en borrador el merge no puede ocurrir."
            ),
            safe_to_repeat=False,
        )

    def write_precheck_reason(self, *, repo: str, issue: int, outcome: PrecheckOutcome, reason: str) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=AutomationMark.appended_to(f"El precheck `{outcome.value}` paro el run: {reason}"),
            safe_to_repeat=False,
        )

    def close_parent(self, *, repo: str, issue: int, subissue_count: int) -> None:
        self._run(
            [
                "gh",
                "issue",
                "close",
                str(issue),
                "--repo",
                repo,
                "--comment",
                AutomationMark.appended_to(
                    f"Las {subissue_count} subissue(s) de esta feature estan todas cerradas, asi que esta feature "
                    "se cierra con ellas."
                ),
            ],
            safe_to_repeat=False,
        )

    def publish_findings(self, *, repo: str, issue: int, history: FindingsHistory, debt: DeclaredDebt) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=VetoFindingsComment.rendered(history, debt),
            safe_to_repeat=False,
        )

    def publish_catch_up_conflict(self, *, repo: str, issue: int, paths: tuple[str, ...]) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=CatchUpConflictComment.rendered(paths),
            safe_to_repeat=False,
        )

    def publish_kept_worktree(self, *, repo: str, issue: int, path: str, retirement: WorktreeRetirement) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=KeptWorktreeComment.rendered(path=path, retirement=retirement),
            safe_to_repeat=False,
        )

    def find_finding(self, *, repo: str, issue: int, finding_id: str) -> Finding | None:
        published = [
            body
            for body in self._comment_bodies(repo=repo, issue=issue)
            if VetoFindingsComment.is_the_veto_findings(body)
        ]
        if not published:
            return None

        return VetoFindingsComment.finding_of(published[-1], finding_id)

    @staticmethod
    def _edit_of(*, repo: str, issue: int, add: IssueLabel, remove: IssueLabel | None) -> list[str]:
        argv = ["gh", "issue", "edit", str(issue), "--repo", repo, "--add-label", add.value]
        if remove is None:
            return argv

        return [*argv, "--remove-label", remove.value]

    def _edit_with_label_fallback(self, argv: list[str], *, repo: str, issue: int, add: IssueLabel) -> None:
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code == 0:
            return

        missing = _LABEL_MISSING.search(outcome.output.stderr)
        if not missing or missing.group(1) != add.value:
            raise GhCommandFailedError(f"gh issue edit failed for {repo}#{issue}: {outcome.reason}")

        self._create_label(repo=repo, name=add.value)
        retried = self._call.run(argv, stdin="", safe_to_repeat=True)
        if retried.output.code != 0:
            raise GhCommandFailedError(
                f"gh issue edit failed for {repo}#{issue} even after creating {add.value!r}: {retried.reason}"
            )

    def _create_label(self, *, repo: str, name: str) -> None:
        outcome = self._call.run(
            [
                "gh",
                "label",
                "create",
                name,
                "--repo",
                repo,
                "--color",
                _LABEL_COLOR,
                "--description",
                _LABEL_DESCRIPTION,
            ],
            stdin="",
            safe_to_repeat=False,
        )
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"gh label create failed for {repo}/{name}: {outcome.reason}")

    def _run(self, argv: list[str], *, stdin: str = "", safe_to_repeat: bool) -> ProcessOutput:
        outcome = self._call.run(argv, stdin=stdin, safe_to_repeat=safe_to_repeat)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return outcome.output

    @staticmethod
    def _decoded(output: ProcessOutput) -> object:
        try:
            return json.loads(output.stdout)
        except json.JSONDecodeError as error:
            raise UnreadableIssueError(f"gh did not return JSON: {error}") from error

    @classmethod
    def _decoded_object(cls, output: ProcessOutput) -> dict[str, object]:
        data = cls._decoded(output)
        if not isinstance(data, dict):
            raise UnreadableIssueError(f"gh has to return an object, not {type(data).__name__}")

        return data

    @classmethod
    def _decoded_array(cls, output: ProcessOutput) -> list[dict[str, object]]:
        data = cls._decoded(output)
        if not isinstance(data, list):
            raise UnreadableIssueError(f"gh has to return an array, not {type(data).__name__}")

        return data

    @classmethod
    def _sub_issue_from(cls, payload: GhSubIssuePayload) -> SubIssue:
        parsed = SubissueBody.parse(payload.body)
        heading = cls._heading_of(payload.title)

        return SubIssue(
            number=payload.number,
            slice_id=SliceIdentity(ordinal=int(heading["ordinal"]), name=heading["name"], user_story=heading["key"]),
            summary=heading["summary"],
            title=payload.title,
            state=payload.state,
            repo=parsed.repo,
            intention=parsed.intention,
            criteria=parsed.criteria,
            decisions=parsed.decisions,
            signal=parsed.signal,
            excludes=parsed.excludes,
            replaces=parsed.replaces,
            run=parsed.run,
            label=cls._label_of(payload.labels),
            design_names=parsed.designs,
        )

    @classmethod
    def _heading_of(cls, title: str) -> re.Match[str]:
        matched = cls.SLICE_HEADING.match(title)
        if not matched:
            raise UnreadableIssueError(f"the subissue title does not open with `slice-NN (name):`: {title!r}")

        return matched

    @staticmethod
    def _label_of(labels: list[GhLabelPayload]) -> IssueLabel | None:
        known = set(IssueLabel)
        retired = set(RetiredIssueLabel)
        for label in labels:
            if label.name in retired:
                gone = RetiredIssueLabel(label.name)
                raise RetiredLabelError(
                    f"the subissue carries `{gone}`, a label this program no longer reads; "
                    f"change it by hand for `{gone.replacement}`"
                )
            if label.name in known:
                return IssueLabel(label.name)

        return None

    @staticmethod
    def _slice_number(child: SubIssue) -> int:
        return child.slice_id.ordinal
