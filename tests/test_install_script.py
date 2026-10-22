from __future__ import annotations

import shutil
import stat
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT

from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.process import ProcessOutput

_SCRIPT = _ROOT / "install.sh"
_SYSTEM_TOOLS = ("mktemp", "rm", "chmod", "awk", "cat")
_REPOSITORY = "alcaptar/slice-runner"
_LATEST = "v0.1.0"

_FAKE_GH = """#!/bin/sh
echo "gh $*" >> "$CALLS"
case "$1 $2" in
"auth status") exit "${GH_AUTH_EXIT:-0}" ;;
"release view") echo "$LATEST" ;;
"release download")
    while [ $# -gt 0 ]; do
        if [ "$1" = "--dir" ]; then directory="$2"; fi
        shift
    done
    : > "$directory/slice_runner-0.1.0-py3-none-any.whl"
    ;;
esac
"""

_FAKE_UV = """#!/bin/sh
echo "uv $*" >> "$CALLS"
if [ "$1 $2 $3" = "tool dir --bin" ]; then echo "$UV_BIN"; fi
if [ "$1 $2" = "tool list" ] && [ -f "$UV_TOOLS" ]; then cat "$UV_TOOLS"; fi
if [ "$1 $2" = "tool install" ]; then
    printf 'slice-runner %s\\n- slice-runner\\n' "$LATEST" > "$UV_TOOLS"
    printf '#!/bin/sh\\necho "$0 $*" >> "$CALLS"\\n' > "$UV_BIN/slice-runner"
    chmod +x "$UV_BIN/slice-runner"
fi
"""

_FAKE_SLICE_RUNNER = """#!/bin/sh
echo "$0 $*" >> "$CALLS"
"""


@dataclass(frozen=True)
class Machine:
    doubles: Path
    system: Path
    tool_bin: Path
    tools: Path
    calls: Path

    def install(self, name: str, content: str, *, directory: Path) -> None:
        target = directory / name
        target.write_text(content, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IEXEC)

    def with_uv(self) -> Machine:
        self.install("uv", _FAKE_UV, directory=self.doubles)
        return self

    def with_gh(self) -> Machine:
        self.install("gh", _FAKE_GH, directory=self.doubles)
        return self

    def with_slice_runner_installed(self, *, version: str = _LATEST) -> Machine:
        self.install("slice-runner", _FAKE_SLICE_RUNNER, directory=self.tool_bin)
        self.tools.write_text(f"slice-runner {version}\n- slice-runner\n", encoding="utf-8")
        return self

    def run_script(self, *, tool_bin_on_path: bool = False, gh_auth_exit: int = 0) -> ProcessOutput:
        path = ":".join([str(self.doubles), *([str(self.tool_bin)] if tool_bin_on_path else []), str(self.system)])
        argv = [
            "env",
            f"PATH={path}",
            f"CALLS={self.calls}",
            f"UV_BIN={self.tool_bin}",
            f"UV_TOOLS={self.tools}",
            f"LATEST={_LATEST}",
            f"GH_AUTH_EXIT={gh_auth_exit}",
            "/bin/sh",
            str(_SCRIPT),
        ]
        return Real.process().run(argv, stdin="", cwd=str(self.doubles))

    def recorded_calls(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []


class InstallScriptCase:
    @pytest.fixture
    def machine(self, tmp_path: Path) -> Machine:
        doubles = tmp_path / "doubles"
        system = tmp_path / "system"
        tool_bin = tmp_path / "uv-bin"
        for directory in (doubles, system, tool_bin):
            directory.mkdir()
        for tool in _SYSTEM_TOOLS:
            (system / tool).symlink_to(str(shutil.which(tool)))
        return Machine(
            doubles=doubles,
            system=system,
            tool_bin=tool_bin,
            tools=tmp_path / "tools.txt",
            calls=tmp_path / "calls.log",
        )


@pytest.mark.integration
class TestFirstInstallation(InstallScriptCase):
    def test_it_downloads_the_latest_wheel_installs_it_and_runs_update_by_absolute_path(self, machine: Machine) -> None:
        result = machine.with_uv().with_gh().run_script(tool_bin_on_path=True)
        calls = machine.recorded_calls()

        assert result.code == 0, result.stderr
        download = next(call for call in calls if call.startswith("gh release download"))
        assert download.startswith(f"gh release download {_LATEST} ")
        assert f"--repo {_REPOSITORY}" in download
        assert "slice_runner-*-py3-none-any.whl" in download
        install = next(call for call in calls if call.startswith("uv tool install"))
        assert install.endswith("slice_runner-0.1.0-py3-none-any.whl")
        assert calls.index(download) < calls.index(install)
        assert calls[-1] == f"{machine.tool_bin}/slice-runner update"


@pytest.mark.integration
class TestAlreadyInstalled(InstallScriptCase):
    def test_at_the_latest_version_it_installs_nothing_and_only_runs_update(self, machine: Machine) -> None:
        result = machine.with_uv().with_gh().with_slice_runner_installed().run_script(tool_bin_on_path=True)
        calls = machine.recorded_calls()

        assert result.code == 0, result.stderr
        assert not any(call.startswith("gh release download") for call in calls)
        assert not any(call.startswith("uv tool install") for call in calls)
        assert calls[-1] == f"{machine.tool_bin}/slice-runner update"

    def test_an_older_version_is_replaced_by_the_latest_wheel_before_update_because_it_may_not_have_update(
        self, machine: Machine
    ) -> None:
        result = (
            machine.with_uv().with_gh().with_slice_runner_installed(version="v0.0.0").run_script(tool_bin_on_path=True)
        )
        calls = machine.recorded_calls()

        assert result.code == 0, result.stderr
        download = next(call for call in calls if call.startswith("gh release download"))
        assert download.startswith(f"gh release download {_LATEST} ")
        install = next(call for call in calls if call.startswith("uv tool install"))
        assert install.startswith("uv tool install --force ")
        assert install.endswith("slice_runner-0.1.0-py3-none-any.whl")
        assert calls.index(download) < calls.index(install)
        assert calls[-1] == f"{machine.tool_bin}/slice-runner update"

    def test_a_program_uv_does_not_list_is_reinstalled_from_the_latest_wheel(self, machine: Machine) -> None:
        machine.with_uv().with_gh()
        machine.install("slice-runner", _FAKE_SLICE_RUNNER, directory=machine.tool_bin)

        result = machine.run_script(tool_bin_on_path=True)

        assert result.code == 0, result.stderr
        assert any(call.startswith("uv tool install --force ") for call in machine.recorded_calls())

    def test_a_refused_update_makes_the_script_fail_too(self, machine: Machine) -> None:
        machine.with_uv().with_gh().with_slice_runner_installed()
        machine.install("slice-runner", "#!/bin/sh\nexit 7\n", directory=machine.tool_bin)

        assert machine.run_script(tool_bin_on_path=True).code != 0


@pytest.mark.integration
class TestMissingPrerequisites(InstallScriptCase):
    def test_without_uv_it_fails_before_downloading_and_says_how_to_install_it(self, machine: Machine) -> None:
        result = machine.with_gh().run_script()

        assert result.code != 0
        assert "uv" in result.stderr
        assert "https://docs.astral.sh/uv" in result.stderr
        assert machine.recorded_calls() == []

    def test_without_gh_it_fails_before_downloading_and_says_how_to_install_it(self, machine: Machine) -> None:
        result = machine.with_uv().run_script()

        assert result.code != 0
        assert "gh" in result.stderr
        assert "https://cli.github.com" in result.stderr
        assert not any(call.startswith("uv tool install") for call in machine.recorded_calls())

    def test_without_a_gh_session_it_fails_before_downloading_and_says_to_log_in(self, machine: Machine) -> None:
        result = machine.with_uv().with_gh().run_script(gh_auth_exit=1)

        assert result.code != 0
        assert "gh auth login" in result.stderr
        assert not any(call.startswith("gh release download") for call in machine.recorded_calls())
        assert not any(call.startswith("uv tool install") for call in machine.recorded_calls())


@pytest.mark.integration
class TestToolDirectoryNotOnPath(InstallScriptCase):
    def test_it_finishes_warning_and_saying_how_to_add_the_directory(self, machine: Machine) -> None:
        result = machine.with_uv().with_gh().run_script(tool_bin_on_path=False)
        output = result.stdout + result.stderr

        assert result.code == 0, output
        assert str(machine.tool_bin) in output
        assert "PATH" in output
        assert f'export PATH="{machine.tool_bin}:$PATH"' in output

    def test_it_stays_quiet_about_the_path_when_the_directory_is_on_it(self, machine: Machine) -> None:
        result = machine.with_uv().with_gh().run_script(tool_bin_on_path=True)

        assert "export PATH" not in result.stdout + result.stderr
