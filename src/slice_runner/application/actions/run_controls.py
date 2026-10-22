from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.activity import Activity
from slice_runner.domain.activity_actor import ActivityActor
from slice_runner.domain.control_status import ControlStatus
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.slice_coordinates import SliceCoordinates

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.activity_log import ActivityLog
    from slice_runner.domain.control_command import ControlCommand
    from slice_runner.domain.control_outcome import ControlOutcome
    from slice_runner.domain.control_runner import ControlRunner
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.slice_identity import SliceIdentity


@dataclass(frozen=True, kw_only=True, slots=True)
class RunControlsParams:
    worktree: str
    controls: Controls
    logs: Path
    repo: str
    issue: int
    slice_id: SliceIdentity
    round_in_progress: int


@dataclass(frozen=True, kw_only=True, slots=True)
class RunControlsResult:
    outcome: Outcome
    red_logs: tuple[Path, ...]


class RunControls:
    def __init__(self, *, controls: ControlRunner, activity: ActivityLog) -> None:
        self._controls = controls
        self._activity = activity

    def execute(self, params: RunControlsParams) -> RunControlsResult:
        out = (
            params.logs
            / params.repo
            / str(params.issue)
            / params.slice_id.canonical
            / f"round-{params.round_in_progress}"
        )
        coordinates = SliceCoordinates(repo=params.repo, issue=params.issue, slice_id=params.slice_id.canonical_id)
        self._activity.restart(coordinates)
        outcomes: tuple[ControlOutcome, ...] = ()
        if params.controls.exemption_reason is None:
            outcomes = tuple(
                self._announced_and_run(command, coordinates=coordinates, worktree=params.worktree, out=out)
                for command in params.controls.commands
            )
        red = tuple(
            outcome.log for outcome in outcomes if outcome.status is ControlStatus.RED and outcome.log is not None
        )

        return RunControlsResult(outcome=Outcome.of_the_controls(outcomes), red_logs=red)

    def _announced_and_run(
        self, command: ControlCommand, *, coordinates: SliceCoordinates, worktree: str, out: Path
    ) -> ControlOutcome:
        self._activity.record(
            Activity(coordinates=coordinates, actor=ActivityActor.CONTROLS, tool=command.name, target=command.command)
        )

        return self._controls.run(command, worktree=worktree, out=out)
