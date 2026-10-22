from __future__ import annotations

from typing import Any

import yaml
from conftest import _ROOT

_WORKFLOW = _ROOT / ".github" / "workflows" / "publish-release.yml"
_TUI_DIRECTORY = "tui"
_PLATFORMS = {
    "aarch64-apple-darwin": "macos-latest",
    "x86_64-unknown-linux-gnu": "ubuntu-22.04",
}
_BUILD_COMMAND = "cargo build --release --locked"


class PublishRelease:
    @staticmethod
    def workflow() -> dict[Any, Any]:
        return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    @classmethod
    def triggers(cls) -> dict[str, Any]:
        return cls.workflow()[True]  # type: ignore[no-any-return]

    @classmethod
    def matrix_entries(cls) -> list[dict[str, str]]:
        return list(cls.workflow()["jobs"]["tui"]["strategy"]["matrix"]["include"])

    @classmethod
    def build_steps(cls) -> list[dict[str, Any]]:
        steps = cls.workflow()["jobs"]["tui"]["steps"]
        return [step for step in steps if _BUILD_COMMAND in str(step.get("run", ""))]

    @classmethod
    def all_steps(cls) -> list[dict[str, Any]]:
        return [step for job in cls.workflow()["jobs"].values() for step in job["steps"]]

    @classmethod
    def uploaded_files(cls) -> str:
        runs = (str(step.get("run", "")) for step in cls.all_steps())
        return " ".join(run for run in runs if "gh release upload" in run)


class TestTrigger:
    def test_it_only_runs_when_a_release_is_published(self) -> None:
        assert PublishRelease.triggers() == {"release": {"types": ["published"]}}


class TestPlatforms:
    def test_each_binary_is_built_natively_on_its_own_runner(self) -> None:
        built = {entry["target"]: entry["runner"] for entry in PublishRelease.matrix_entries()}

        assert built == _PLATFORMS

    def test_the_tui_job_runs_on_the_runner_of_the_matrix_entry(self) -> None:
        assert PublishRelease.workflow()["jobs"]["tui"]["runs-on"] == "${{ matrix.runner }}"


class TestBuild:
    def test_the_tui_is_built_in_release_mode_with_the_lock_enforced(self) -> None:
        assert len(PublishRelease.build_steps()) == 1

    def test_cargo_runs_inside_the_tui_directory_so_the_toolchain_file_applies(self) -> None:
        assert PublishRelease.build_steps()[0]["working-directory"] == _TUI_DIRECTORY

    def test_the_toolchain_is_installed_from_the_tui_directory(self) -> None:
        steps = PublishRelease.workflow()["jobs"]["tui"]["steps"]
        installs = [step for step in steps if "rustup toolchain install" in str(step.get("run", ""))]

        assert [step["working-directory"] for step in installs] == [_TUI_DIRECTORY]


class TestAssets:
    def test_the_three_files_are_attached_with_the_names_the_feature_declares(self) -> None:
        uploaded = PublishRelease.uploaded_files()

        assert "slice_runner-" in uploaded
        assert "-py3-none-any.whl" in uploaded
        assert "slice-runner-tui-${{ matrix.target }}" in uploaded

    def test_the_uploads_target_the_release_that_triggered_the_workflow(self) -> None:
        assert PublishRelease.workflow()["env"]["TAG"] == "${{ github.event.release.tag_name }}"
        assert PublishRelease.uploaded_files().count('gh release upload "$TAG"') == 3

    def test_the_workflow_may_write_contents_to_attach_assets(self) -> None:
        assert PublishRelease.workflow()["permissions"] == {"contents": "write"}


class TestInstaller:
    def test_install_sh_is_attached_to_every_release(self) -> None:
        assert 'gh release upload "$TAG" install.sh' in PublishRelease.uploaded_files()
