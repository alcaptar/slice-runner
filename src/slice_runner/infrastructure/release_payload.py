from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadableReleaseError
from slice_runner.domain.published_release import PublishedRelease
from slice_runner.domain.release_version import ReleaseVersion
from slice_runner.infrastructure.contract_model import ContractModel


class ReleasePayload(ContractModel):
    tag: str = Field(alias="tagName", strict=True)
    assets: list[str] = Field(alias="assets", strict=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        projected = {**data, "assets": cls._names(data.get("assets"))}

        return cls._validated(
            projected, "gh release view does not carry a readable tag and files", UnreadableReleaseError
        )

    @staticmethod
    def _names(assets: object) -> object:
        if not isinstance(assets, list):
            return assets

        return [asset.get("name") if isinstance(asset, dict) else asset for asset in assets]

    def to_domain(self) -> PublishedRelease:
        return PublishedRelease(version=ReleaseVersion.of(self.tag), assets=frozenset(self.assets))
