from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from slice_runner.infrastructure.design_captures_manifest import (
    CapturesManifestPayload,
    DesignCapturesManifest,
    MissingManifestPayload,
)
from slice_runner.infrastructure.unreadable_captures_manifest_error import UnreadableCapturesManifestError


class TestTheExampleOfTheManifestContract:
    _CONTRACT: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "design-captures-manifest.json"

    @classmethod
    def _examples(cls) -> list[dict[str, object]]:
        examples: list[dict[str, object]] = json.loads(cls._CONTRACT.read_text(encoding="utf-8"))["examples"]

        return examples

    def test_the_example_with_captures_is_read_by_the_boundary_model(self) -> None:
        read = DesignCapturesManifest.read(json.dumps(self._examples()[0]))

        assert isinstance(read, CapturesManifestPayload)
        assert [capture.design for capture in read.captures] == ["tablero", "detalle"]

    def test_the_example_declaring_the_captures_missing_is_read_by_the_boundary_model(self) -> None:
        read = DesignCapturesManifest.read(json.dumps(self._examples()[1]))

        assert isinstance(read, MissingManifestPayload)
        assert read.missing

    def test_a_manifest_with_one_field_more_than_the_example_is_rejected(self) -> None:
        manifest = {**self._examples()[0], "notes": "unrequested"}

        with pytest.raises(UnreadableCapturesManifestError, match="notes"):
            DesignCapturesManifest.read(json.dumps(manifest))

    def test_a_capture_with_one_field_more_than_the_example_is_rejected(self) -> None:
        first = {**self._examples()[0]["captures"][0], "width": 80}  # type: ignore[index]
        manifest = {"captures": [first]}

        with pytest.raises(UnreadableCapturesManifestError, match="width"):
            DesignCapturesManifest.read(json.dumps(manifest))

    def test_a_missing_manifest_with_one_field_more_is_rejected(self) -> None:
        with pytest.raises(UnreadableCapturesManifestError, match="notes"):
            DesignCapturesManifest.read(json.dumps({"missing": "why", "notes": "unrequested"}))

    @pytest.mark.parametrize("text", ["not json", "[]", '{"captures": "tablero.html"}', "{}"])
    def test_what_is_not_one_of_the_two_shapes_is_unreadable(self, text: str) -> None:
        with pytest.raises(UnreadableCapturesManifestError):
            DesignCapturesManifest.read(text)
