from __future__ import annotations

import json
from typing import Self

from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.unreadable_captures_manifest_error import UnreadableCapturesManifestError


class CapturePayload(ContractModel):
    design: str
    state: str
    file: str


class CapturesManifestPayload(ContractModel):
    captures: tuple[CapturePayload, ...]

    @classmethod
    def of(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, DesignCapturesManifest.WHERE, UnreadableCapturesManifestError)


class MissingManifestPayload(ContractModel):
    missing: str

    @classmethod
    def of(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, DesignCapturesManifest.WHERE, UnreadableCapturesManifestError)


class DesignCapturesManifest:
    WHERE = "the design captures manifest is not one of the two shapes the contract declares"

    @classmethod
    def read(cls, text: str) -> CapturesManifestPayload | MissingManifestPayload:
        data = cls._decoded(text)
        if "missing" in data:
            return MissingManifestPayload.of(data)

        return CapturesManifestPayload.of(data)

    @staticmethod
    def _decoded(text: str) -> dict[str, object]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise UnreadableCapturesManifestError(f"the design captures manifest is not JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableCapturesManifestError(
                f"the design captures manifest has to be an object, not {type(data).__name__}"
            )

        return data
