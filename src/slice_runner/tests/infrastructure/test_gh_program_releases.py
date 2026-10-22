from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.binary_platform import BinaryPlatform
from slice_runner.domain.exceptions import UnreadableReleaseError
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.infrastructure.gh_program_releases import GhProgramReleases
from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError
from slice_runner.tests.doubles import Answer, AnsweringByArgv

if TYPE_CHECKING:
    from collections.abc import Callable

_REPO = "alcaptar/slice-runner"


class DownloadingProcess(Process):
    def __init__(self, *, content: str = "payload", writes: bool = True) -> None:
        self._content = content
        self._writes = writes
        self.argvs: list[list[str]] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.argvs.append(list(argv))
        if self._writes:
            directory = Path(argv[argv.index("--dir") + 1])
            (directory / argv[argv.index("--pattern") + 1]).write_text(self._content, encoding="utf-8")

        return ProcessOutput(code=0, stdout="", stderr="")


class FailingProcess(Process):
    def __init__(self, error: OSError) -> None:
        self._error = error

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        raise self._error


class TestTheLatestRelease:
    _VIEW = ("gh", "release", "view")
    _COMPLETE = (
        '{"tagName":"v0.2.0","assets":[{"name":"slice_runner-0.2.0-py3-none-any.whl","size":10,"state":"uploaded"},'
        '{"name":"slice-runner-tui-aarch64-apple-darwin","size":20}]}'
    )

    @staticmethod
    def _releases(answer: Answer) -> GhProgramReleases:
        return GhProgramReleases(process=AnsweringByArgv(answer), repo=_REPO)

    def test_it_is_the_version_of_the_tag_without_the_v_with_the_names_of_its_files(self) -> None:
        process = AnsweringByArgv(Answer(to=self._VIEW, stdout=self._COMPLETE))

        release = GhProgramReleases(process=process, repo=_REPO).latest()

        assert release.version == ReleaseVersion.of("0.2.0")
        assert release.assets == frozenset(
            {"slice_runner-0.2.0-py3-none-any.whl", "slice-runner-tui-aarch64-apple-darwin"}
        )
        assert process.calls[0].argv == [
            "gh",
            "release",
            "view",
            "--repo",
            _REPO,
            "--json",
            "tagName,assets",
        ]

    def test_a_release_without_files_carries_no_asset_names(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, stdout='{"tagName":"v0.2.0","assets":[]}'))

        assert releases.latest().assets == frozenset()

    def test_a_failing_gh_is_an_unreadable_release_that_carries_the_reason(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, code=1, stderr="HTTP 404"))

        with pytest.raises(UnreadableReleaseError, match="HTTP 404"):
            releases.latest()

    def test_an_answer_that_is_not_the_expected_envelope_is_an_unreadable_release(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, stdout='{"name":"0.2.0"}'))

        with pytest.raises(UnreadableReleaseError):
            releases.latest()

    def test_an_answer_whose_files_have_no_name_is_an_unreadable_release(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, stdout='{"tagName":"v0.2.0","assets":[{"size":10}]}'))

        with pytest.raises(UnreadableReleaseError, match="assets"):
            releases.latest()

    def test_a_tag_that_is_not_a_version_is_an_unreadable_release(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, stdout='{"tagName":"nightly","assets":[]}'))

        with pytest.raises(UnreadableReleaseError, match="nightly"):
            releases.latest()

    def test_an_answer_that_is_not_json_is_an_unreadable_release(self) -> None:
        releases = self._releases(Answer(to=self._VIEW, stdout="not json"))

        with pytest.raises(UnreadableReleaseError):
            releases.latest()

    @pytest.mark.parametrize("error", [ProcessTimedOutError("gh: killed after 5s"), ProcessNotRunnableError("gh")])
    def test_a_gh_that_cannot_run_or_times_out_is_an_unreadable_release(self, error: OSError) -> None:
        with pytest.raises(UnreadableReleaseError):
            GhProgramReleases(process=FailingProcess(error), repo=_REPO).latest()


class TestTheDownloads:
    def test_the_wheel_is_downloaded_by_the_name_the_release_attaches(self) -> None:
        process = DownloadingProcess(content="wheel bytes")

        wheel = GhProgramReleases(process=process, repo=_REPO).wheel(ReleaseVersion.of("0.2.0"))

        assert wheel.name == "slice_runner-0.2.0-py3-none-any.whl"
        assert wheel.read_text(encoding="utf-8") == "wheel bytes"
        assert process.argvs[0][:6] == ["gh", "release", "download", "v0.2.0", "--repo", _REPO]

    def test_the_binary_is_downloaded_by_the_name_of_its_platform(self) -> None:
        process = DownloadingProcess()

        binary = GhProgramReleases(process=process, repo=_REPO).binary(
            ReleaseVersion.of("0.2.0"), BinaryPlatform.LINUX_X86_64
        )

        assert binary.name == "slice-runner-tui-x86_64-unknown-linux-gnu"
        assert "--pattern" in process.argvs[0]

    def test_a_download_that_leaves_no_file_is_an_unreadable_release(self) -> None:
        releases = GhProgramReleases(process=DownloadingProcess(writes=False), repo=_REPO)

        with pytest.raises(UnreadableReleaseError, match=r"slice_runner-0\.2\.0"):
            releases.wheel(ReleaseVersion.of("0.2.0"))

    def test_a_failing_download_carries_the_reason_of_gh(self) -> None:
        process = AnsweringByArgv(Answer(to=("gh", "release", "download"), code=1, stderr="no assets match"))

        with pytest.raises(UnreadableReleaseError, match="no assets match"):
            GhProgramReleases(process=process, repo=_REPO).wheel(ReleaseVersion.of("0.2.0"))
