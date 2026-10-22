from __future__ import annotations

import subprocess
import zipfile
from typing import TYPE_CHECKING

import pytest
from conftest import _ROOT

if TYPE_CHECKING:
    from pathlib import Path

_SKILL = _ROOT / "skills" / "slice-spec"
_PACKAGED = "slice_runner/skills/slice-spec"


@pytest.mark.integration
class TestTheWheelCarriesTheSkill:
    @pytest.fixture(scope="class")
    @classmethod
    def packaged(cls, tmp_path_factory: pytest.TempPathFactory) -> set[str]:
        out: Path = tmp_path_factory.mktemp("wheel")
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(out)], cwd=_ROOT, check=True, capture_output=True, timeout=300
        )
        [wheel] = out.glob("slice_runner-*.whl")
        with zipfile.ZipFile(wheel) as archive:
            return set(archive.namelist())

    def test_the_skill_manifest_is_inside_the_wheel(self, packaged: set[str]) -> None:
        assert f"{_PACKAGED}/SKILL.md" in packaged

    def test_every_reference_of_the_skill_is_inside_the_wheel(self, packaged: set[str]) -> None:
        references = sorted(path for path in (_SKILL / "references").rglob("*") if path.is_file())

        assert references
        missing = [
            str(path.relative_to(_SKILL))
            for path in references
            if f"{_PACKAGED}/{path.relative_to(_SKILL)}" not in packaged
        ]
        assert missing == []

    def test_every_file_of_the_skill_is_inside_the_wheel(self, packaged: set[str]) -> None:
        files = sorted(path.relative_to(_SKILL) for path in _SKILL.rglob("*") if path.is_file())

        assert [str(path) for path in files if f"{_PACKAGED}/{path}" not in packaged] == []
