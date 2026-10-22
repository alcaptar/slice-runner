from __future__ import annotations

import json
import re
import tomllib
from typing import Any

import yaml
from conftest import _ROOT

_CONFIG = _ROOT / "release-please-config.json"
_MANIFEST = _ROOT / ".release-please-manifest.json"
_WORKFLOW = _ROOT / ".github" / "workflows" / "release-please.yml"
_PYPROJECT = _ROOT / "pyproject.toml"
_CARGO_LOCK = _ROOT / "tui" / "Cargo.lock"
_TOKEN_STEP_ID = "app-token"
_RELEASE_ENVIRONMENT = "release"


class ReleasePlease:
    @staticmethod
    def config() -> dict[str, Any]:
        return json.loads(_CONFIG.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    @staticmethod
    def manifest() -> dict[str, str]:
        return json.loads(_MANIFEST.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    @staticmethod
    def workflow() -> dict[Any, Any]:
        return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    @classmethod
    def root_package(cls) -> dict[str, Any]:
        return cls.config()["packages"]["."]  # type: ignore[no-any-return]

    @classmethod
    def extra_files(cls) -> list[Any]:
        return list(cls.root_package().get("extra-files", []))

    @classmethod
    def release_please_step(cls) -> dict[str, Any]:
        steps = cls.workflow()["jobs"]["release-please"]["steps"]
        matching = [step for step in steps if str(step.get("uses", "")).startswith("googleapis/release-please-action@")]
        assert len(matching) == 1
        return matching[0]  # type: ignore[no-any-return]

    @classmethod
    def token_step(cls) -> dict[str, Any]:
        steps = cls.workflow()["jobs"]["release-please"]["steps"]
        matching = [step for step in steps if str(step.get("uses", "")).startswith("actions/create-github-app-token@")]
        assert len(matching) == 1
        return matching[0]  # type: ignore[no-any-return]

    @classmethod
    def paths_declared(cls) -> set[str]:
        return {entry if isinstance(entry, str) else entry["path"] for entry in cls.extra_files()}

    @classmethod
    def entry_for(cls, path: str) -> dict[str, Any]:
        matching = [entry for entry in cls.extra_files() if isinstance(entry, dict) and entry["path"] == path]
        assert matching, f"{path} is not declared as an object entry"
        return matching[0]


class TestWorkflow:
    def test_it_runs_on_every_push_to_master(self) -> None:
        triggers = ReleasePlease.workflow()[True]

        assert triggers == {"push": {"branches": ["master"]}}

    def test_release_please_receives_the_token_the_app_token_step_generates(self) -> None:
        step = ReleasePlease.release_please_step()

        assert step["with"]["token"] == f"${{{{ steps.{_TOKEN_STEP_ID}.outputs.token }}}}"
        assert ReleasePlease.token_step()["id"] == _TOKEN_STEP_ID

    def test_the_app_token_is_generated_from_the_secrets_of_the_release_environment(self) -> None:
        job = ReleasePlease.workflow()["jobs"]["release-please"]
        inputs = ReleasePlease.token_step()["with"]

        assert job["environment"] == _RELEASE_ENVIRONMENT
        assert re.fullmatch(r"\$\{\{ secrets\.\w+ \}\}", inputs["client-id"])
        assert re.fullmatch(r"\$\{\{ secrets\.\w+ \}\}", inputs["private-key"])

    def test_release_please_reads_the_config_and_manifest_this_repo_declares(self) -> None:
        inputs = ReleasePlease.release_please_step()["with"]

        assert inputs["config-file"] == _CONFIG.name
        assert inputs["manifest-file"] == _MANIFEST.name


class TestConfig:
    def test_a_single_package_at_the_root_is_released_as_simple(self) -> None:
        assert list(ReleasePlease.config()["packages"]) == ["."]
        assert ReleasePlease.root_package()["release-type"] == "simple"

    def test_the_tag_is_the_version_prefixed_with_v_and_no_component(self) -> None:
        config = ReleasePlease.config()

        assert config["include-v-in-tag"] is True
        assert config["include-component-in-tag"] is False

    def test_the_python_manifest_is_a_file_to_update(self) -> None:
        assert "pyproject.toml" in ReleasePlease.paths_declared()

    def test_the_rust_manifest_is_a_file_to_update(self) -> None:
        assert "tui/Cargo.toml" in ReleasePlease.paths_declared()

    def test_the_lock_entry_of_the_tui_is_a_file_to_update(self) -> None:
        entry = ReleasePlease.entry_for("tui/Cargo.lock")

        assert entry["type"] == "toml"
        assert entry["jsonpath"] == '$.package[?(@.name.value=="slice-runner-tui")].version'

    def test_the_lock_entry_of_the_program_is_a_file_to_update(self) -> None:
        entry = ReleasePlease.entry_for("uv.lock")

        assert entry["type"] == "toml"
        assert entry["jsonpath"] == '$.package[?(@.name.value=="slice-runner")].version'

    def test_the_first_release_is_zero_point_one_and_not_the_default_one_point_zero(self) -> None:
        assert ReleasePlease.root_package()["initial-version"] == "0.1.0"

    def test_before_one_point_zero_a_breaking_change_bumps_the_minor(self) -> None:
        config = ReleasePlease.config()

        assert config["bump-minor-pre-major"] is True


class TestVersionsAgree:
    def test_the_manifest_version_is_the_one_in_pyproject(self) -> None:
        pyproject = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))

        assert ReleasePlease.manifest() == {".": pyproject["project"]["version"]}

    def test_the_tui_manifest_and_lock_carry_the_same_version_as_pyproject(self) -> None:
        pyproject = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
        cargo = tomllib.loads((_ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
        lock = tomllib.loads(_CARGO_LOCK.read_text(encoding="utf-8"))["package"]
        tui_lock = [package["version"] for package in lock if package["name"] == "slice-runner-tui"]

        assert (cargo, tui_lock) == (pyproject, [pyproject])
