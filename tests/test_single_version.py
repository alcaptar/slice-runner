from __future__ import annotations

import tomllib

from conftest import _ROOT


class TestTheVersionOfEveryManifest:
    @staticmethod
    def _pyproject_version() -> str:
        document = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(document["project"]["version"])

    @staticmethod
    def _cargo_version() -> str:
        document = tomllib.loads((_ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        return str(document["package"]["version"])

    @staticmethod
    def _cargo_lock_version() -> str:
        document = tomllib.loads((_ROOT / "tui" / "Cargo.lock").read_text(encoding="utf-8"))
        entries = [entry for entry in document["package"] if entry["name"] == "slice-runner-tui"]
        assert len(entries) == 1
        return str(entries[0]["version"])

    @staticmethod
    def _uv_lock_version() -> str:
        document = tomllib.loads((_ROOT / "uv.lock").read_text(encoding="utf-8"))
        entries = [entry for entry in document["package"] if entry["name"] == "slice-runner"]
        assert len(entries) == 1
        return str(entries[0]["version"])

    def test_the_wheel_the_interface_and_their_lock_entries_declare_the_same_version(self) -> None:
        versions = {
            "pyproject.toml": self._pyproject_version(),
            "uv.lock": self._uv_lock_version(),
            "tui/Cargo.toml": self._cargo_version(),
            "tui/Cargo.lock": self._cargo_lock_version(),
        }

        assert len(set(versions.values())) == 1, versions
