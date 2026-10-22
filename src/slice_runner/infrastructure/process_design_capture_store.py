from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.design_capture import DesignCapture
from slice_runner.domain.design_capture_store import DesignCaptureStore
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.missing_design_captures import MissingDesignCaptures
from slice_runner.infrastructure.design_captures_manifest import (
    CapturePayload,
    CapturesManifestPayload,
    DesignCapturesManifest,
)
from slice_runner.infrastructure.unreadable_captures_manifest_error import UnreadableCapturesManifestError

if TYPE_CHECKING:
    from slice_runner.domain.design import Design
    from slice_runner.infrastructure.process import Process


class ProcessDesignCaptureStore(DesignCaptureStore):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def clear(self, *, worktree: str) -> None:
        argv = ["rm", "-rf", "--", DesignCapturesDirectory.of(worktree)]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise OSError(f"the design captures of {worktree} could not be cleared: {output.reason(tool=argv[0])}")

    def read(self, *, worktree: str, designs: tuple[Design, ...]) -> DesignCaptures | MissingDesignCaptures:
        manifest_path = DesignCapturesDirectory.manifest_of(worktree)
        argv = ["cat", manifest_path]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            return MissingDesignCaptures(reason=f"{manifest_path} could not be read: {output.reason(tool=argv[0])}")
        try:
            manifest = DesignCapturesManifest.read(output.stdout)
        except UnreadableCapturesManifestError as unreadable:
            return MissingDesignCaptures(reason=str(unreadable))
        if not isinstance(manifest, CapturesManifestPayload):
            return MissingDesignCaptures(reason=manifest.missing)

        return self._found(worktree=worktree, manifest=manifest, designs=designs)

    def _found(
        self, *, worktree: str, manifest: CapturesManifestPayload, designs: tuple[Design, ...]
    ) -> DesignCaptures | MissingDesignCaptures:
        if not manifest.captures:
            return MissingDesignCaptures(reason="the design captures manifest lists no captures")
        cited = {design.name for design in designs}
        for capture in manifest.captures:
            if capture.design not in cited:
                return MissingDesignCaptures(
                    reason=f"the manifest has a capture of the design {capture.design!r}, which the slice does not cite"
                )
            path = DesignCapturesDirectory.file_of(worktree, capture.file)
            if not self._exists(path):
                return MissingDesignCaptures(reason=f"the capture file {capture.file} does not exist at {path}")

        return DesignCaptures(
            captures=tuple(self._captured(worktree, capture) for capture in manifest.captures),
        )

    @staticmethod
    def _captured(worktree: str, capture: CapturePayload) -> DesignCapture:
        return DesignCapture(
            design=capture.design, state=capture.state, path=DesignCapturesDirectory.file_of(worktree, capture.file)
        )

    def _exists(self, path: str) -> bool:
        return self._process.run(["test", "-f", path], stdin="").code == 0
