from __future__ import annotations

import json

import pytest

from slice_runner.domain.design_capture import DesignCapture
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.missing_design_captures import MissingDesignCaptures
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.design_mother import DesignMother

_WORKTREE = "/worktree"


class _CapturesDirectory:
    def __init__(self) -> None:
        self._answers: list[Answer] = []

    def holding(self, *names: str) -> _CapturesDirectory:
        for name in names:
            self._answers.append(Answer.to_exactly("test", "-f", DesignCapturesDirectory.file_of(_WORKTREE, name)))

        return self

    def lacking(self, *names: str) -> _CapturesDirectory:
        for name in names:
            self._answers.append(
                Answer.to_exactly("test", "-f", DesignCapturesDirectory.file_of(_WORKTREE, name), code=1)
            )

        return self

    def with_manifest(self, text: str) -> _CapturesDirectory:
        self._answers.append(Answer.to_exactly("cat", DesignCapturesDirectory.manifest_of(_WORKTREE), stdout=text))

        return self

    def with_manifest_of(self, manifest: dict[str, object]) -> _CapturesDirectory:
        return self.with_manifest(json.dumps(manifest))

    def without_manifest(self) -> _CapturesDirectory:
        manifest = DesignCapturesDirectory.manifest_of(_WORKTREE)
        self._answers.append(
            Answer.to_exactly("cat", manifest, code=1, stderr=f"cat: {manifest}: No such file or directory")
        )

        return self

    def read(self) -> DesignCaptures | MissingDesignCaptures:
        store = ProcessDesignCaptureStore(process=AnsweringByArgv(*self._answers))

        return store.read(worktree=_WORKTREE, designs=(DesignMother.board(), DesignMother.detail()))


class TestClearingTheCapturesDirectory:
    CLEARING = ("rm", "-rf", "--", DesignCapturesDirectory.of(_WORKTREE))

    def test_the_directory_the_previous_round_left_is_removed_with_everything_in_it(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.CLEARING))

        ProcessDesignCaptureStore(process=process).clear(worktree=_WORKTREE)

        assert process.ran(*self.CLEARING)

    def test_clearing_a_worktree_that_never_had_the_directory_is_not_an_error(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.CLEARING))

        ProcessDesignCaptureStore(process=process).clear(worktree=_WORKTREE)

        assert process.times_invoked("rm") == 1

    def test_the_rest_of_the_worktree_is_left_alone(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.CLEARING))

        ProcessDesignCaptureStore(process=process).clear(worktree=_WORKTREE)

        assert [call.argv for call in process.calls] == [list(self.CLEARING)]

    def test_a_directory_that_cannot_be_removed_says_why(self) -> None:
        process = AnsweringByArgv(Answer.to_exactly(*self.CLEARING, code=1, stderr="rm: Permission denied"))

        with pytest.raises(OSError, match="Permission denied"):
            ProcessDesignCaptureStore(process=process).clear(worktree=_WORKTREE)


class TestReadingTheCapturesTheImplementerLeft:
    def test_a_manifest_of_two_captures_gives_both_with_the_absolute_path_of_each_file(self) -> None:
        read = (
            _CapturesDirectory()
            .with_manifest_of(
                {
                    "captures": [
                        {"design": "tablero", "state": "a 80 columnas", "file": "tablero.html"},
                        {"design": "detalle", "state": "con un hallazgo", "file": "detalle.html"},
                    ]
                }
            )
            .holding("tablero.html", "detalle.html")
            .read()
        )

        assert read == DesignCaptures(
            captures=(
                DesignCapture(
                    design="tablero",
                    state="a 80 columnas",
                    path=DesignCapturesDirectory.file_of(_WORKTREE, "tablero.html"),
                ),
                DesignCapture(
                    design="detalle",
                    state="con un hallazgo",
                    path=DesignCapturesDirectory.file_of(_WORKTREE, "detalle.html"),
                ),
            )
        )

    def test_an_unreadable_manifest_means_no_captures_and_says_why(self) -> None:
        read = _CapturesDirectory().with_manifest("{not json").read()

        assert isinstance(read, MissingDesignCaptures)
        assert "not JSON" in read.reason

    def test_a_manifest_that_declares_the_captures_missing_carries_its_reason(self) -> None:
        read = _CapturesDirectory().with_manifest_of({"missing": "no terminal here"}).read()

        assert read == MissingDesignCaptures(reason="no terminal here")

    def test_a_capture_of_a_design_the_slice_does_not_cite_means_no_captures_and_says_which(self) -> None:
        read = (
            _CapturesDirectory()
            .with_manifest_of({"captures": [{"design": "otro", "state": "x", "file": "otro.html"}]})
            .read()
        )

        assert isinstance(read, MissingDesignCaptures)
        assert "otro" in read.reason

    def test_a_capture_whose_file_does_not_exist_means_no_captures_and_says_which(self) -> None:
        read = (
            _CapturesDirectory()
            .with_manifest_of({"captures": [{"design": "tablero", "state": "x", "file": "ghost.html"}]})
            .lacking("ghost.html")
            .read()
        )

        assert isinstance(read, MissingDesignCaptures)
        assert "ghost.html" in read.reason

    def test_a_single_missing_file_discards_the_whole_manifest(self) -> None:
        read = (
            _CapturesDirectory()
            .with_manifest_of(
                {
                    "captures": [
                        {"design": "tablero", "state": "x", "file": "tablero.html"},
                        {"design": "detalle", "state": "y", "file": "ghost.html"},
                    ]
                }
            )
            .holding("tablero.html")
            .lacking("ghost.html")
            .read()
        )

        assert isinstance(read, MissingDesignCaptures)

    def test_no_manifest_at_all_means_no_captures_and_says_so(self) -> None:
        read = _CapturesDirectory().without_manifest().read()

        assert isinstance(read, MissingDesignCaptures)
        assert DesignCapturesDirectory.MANIFEST in read.reason

    def test_a_manifest_listing_no_captures_means_no_captures(self) -> None:
        read = _CapturesDirectory().with_manifest_of({"captures": []}).read()

        assert isinstance(read, MissingDesignCaptures)
