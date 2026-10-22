from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.feature_slice import FeatureSlice


class FeatureSliceMother:
    PARENT: ClassVar[int] = 140
    NAME: ClassVar[str] = "follow-speaks-json"

    @classmethod
    def of_the_feature(cls) -> FeatureSlice:
        return FeatureSlice(parent=cls.PARENT, name=cls.NAME)
