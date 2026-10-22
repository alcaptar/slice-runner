from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from slice_runner.application.actions.mount_comparison import MountComparison, MountComparisonParams
from slice_runner.application.queries.read_design_captures import ReadDesignCaptures, ReadDesignCapturesParams
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.infrastructure.process_comparison_pages import ProcessComparisonPages
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.doubles import Answer, AnsweringByArgv
from slice_runner.tests.mothers.design_mother import DesignMother

if TYPE_CHECKING:
    from slice_runner.domain.design import Design


class _Worktree:
    PATH = "/worktree"
    FIRST_ROUND_CAPTURE = "<p>capture of the first round</p>"
    SECOND_ROUND_CAPTURE = "<p>capture of the second round</p>"
    BOARD_CAPTURE = "<p>board as drawn</p>"
    DETAIL_CAPTURE = "<p>detail as drawn</p>"

    def __init__(self) -> None:
        self._found: list[Answer] = []
        self.process = AnsweringByArgv()

    def captured(self, manifest: dict[str, object], **files: str) -> _Worktree:
        self._found = [
            Answer.to_exactly("cat", DesignCapturesDirectory.manifest_of(self.PATH), stdout=json.dumps(manifest))
        ]
        for name, content in files.items():
            file = name.replace("_", ".")
            path = DesignCapturesDirectory.file_of(self.PATH, file)
            self._found.append(Answer.to_exactly("test", "-f", path))
            if file.endswith(".html"):
                self._found.append(Answer.to_exactly("cat", path, stdout=content))

        return self

    def without_manifest(self) -> _Worktree:
        manifest = DesignCapturesDirectory.manifest_of(self.PATH)
        self._found = [Answer.to_exactly("cat", manifest, code=1, stderr=f"cat: {manifest}: No such file or directory")]

        return self

    def captured_the_board_and_the_detail(self) -> _Worktree:
        return self.captured(
            {
                "captures": [
                    {"design": "tablero", "state": "board at 80 columns", "file": "tablero.html"},
                    {"design": "detalle", "state": "detail with a finding", "file": "detalle.html"},
                ]
            },
            tablero_html=self.BOARD_CAPTURE,
            detalle_html=self.DETAIL_CAPTURE,
        )

    def passing_through_open_pull_request(self, *designs: Design) -> None:
        self.process = AnsweringByArgv(
            *self._found,
            Answer.to_exactly("mkdir", "-p", DesignCapturesDirectory.of(self.PATH)),
            Answer.to_exactly("tee", DesignCapturesDirectory.comparison_of(self.PATH)),
        )
        captures = ReadDesignCaptures(captures=ProcessDesignCaptureStore(process=self.process)).execute(
            ReadDesignCapturesParams(worktree=self.PATH, designs=designs)
        )
        MountComparison(pages=ProcessComparisonPages(process=self.process)).execute(
            MountComparisonParams(worktree=self.PATH, designs=designs, captures=captures)
        )

    @property
    def wrote_a_page(self) -> bool:
        return self.process.invoked("tee")

    def page_text(self) -> str:
        return next(call.stdin for call in self.process.calls if call.argv[0] == "tee")


class TestMountingTheComparisonPage:
    def test_two_captures_of_two_designs_leave_two_pairs_each_capture_next_to_the_design_it_names(self) -> None:
        worktree = _Worktree().captured_the_board_and_the_detail()

        worktree.passing_through_open_pull_request(DesignMother.board(), DesignMother.detail())

        page = worktree.page_text()
        pairs = page.split('<section class="pair">')[1:]
        assert len(pairs) == 2
        assert html.escape(DesignMother.BOARD_HTML) in pairs[0]
        assert html.escape(_Worktree.BOARD_CAPTURE) in pairs[0]
        assert html.escape(_Worktree.DETAIL_CAPTURE) not in pairs[0]
        assert html.escape(DesignMother.DETAIL_HTML) in pairs[1]
        assert html.escape(_Worktree.DETAIL_CAPTURE) in pairs[1]

    def test_a_png_capture_is_shown_as_an_image_next_to_its_design(self) -> None:
        worktree = _Worktree().captured(
            {"captures": [{"design": "tablero", "state": "board", "file": "tablero.png"}]}, tablero_png="png"
        )

        worktree.passing_through_open_pull_request(DesignMother.board())

        assert '<img src="tablero.png"' in worktree.page_text()

    def test_a_missing_manifest_leaves_the_page_with_the_design_and_the_reason(self) -> None:
        worktree = _Worktree().captured({"missing": "no terminal to draw the screen"})

        worktree.passing_through_open_pull_request(DesignMother.board())

        page = worktree.page_text()
        assert html.escape(DesignMother.BOARD_HTML) in page
        assert "no terminal to draw the screen" in page

    def test_a_worktree_without_any_manifest_still_leaves_the_page_with_the_design_and_the_reason(self) -> None:
        worktree = _Worktree().without_manifest()

        worktree.passing_through_open_pull_request(DesignMother.board())

        page = worktree.page_text()
        assert html.escape(DesignMother.BOARD_HTML) in page
        assert "could not be read" in page

    def test_a_slice_that_cites_no_design_writes_no_page(self) -> None:
        worktree = _Worktree()

        worktree.passing_through_open_pull_request()

        assert not worktree.wrote_a_page

    def test_the_page_of_a_correction_round_does_not_hold_the_capture_of_the_first_round(self) -> None:
        worktree = _Worktree()
        manifest: dict[str, object] = {"captures": [{"design": "tablero", "state": "board", "file": "tablero.html"}]}
        worktree.captured(manifest, tablero_html=_Worktree.FIRST_ROUND_CAPTURE)
        worktree.passing_through_open_pull_request(DesignMother.board())

        worktree.captured(manifest, tablero_html=_Worktree.SECOND_ROUND_CAPTURE)
        worktree.passing_through_open_pull_request(DesignMother.board())

        page = worktree.page_text()
        assert html.escape(_Worktree.SECOND_ROUND_CAPTURE) in page
        assert html.escape(_Worktree.FIRST_ROUND_CAPTURE) not in page
